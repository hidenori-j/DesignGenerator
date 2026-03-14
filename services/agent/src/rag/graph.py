"""LangGraph agent: 4-step RAG pipeline for design generation."""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.rag.decomposer import DecomposedQuery, decompose_query
from src.rag.prompt_builder import GenerationPrompt, build_generation_prompt
from src.rag.reranker import RankedResult, rerank
from src.retrieval.search import multi_query_search

logger = logging.getLogger(__name__)


class AgentState(TypedDict, total=False):
    prompt: str
    brand: str | None
    reference_mode: str
    resolution: dict[str, int] | None
    style_reference_ids: list[str]
    layout_reference_ids: list[str]
    decomposed: DecomposedQuery | None
    search_results: list[tuple[str, float, dict]]
    ranked_results: list[RankedResult]
    generation_prompt: GenerationPrompt | None
    error: str | None
    step: str


async def decompose_node(state: AgentState) -> dict[str, Any]:
    """Step 1: Decompose user prompt into structured design elements."""
    logger.info("Step 1: Query decomposition")
    prompt = state["prompt"]
    try:
        decomposed = await decompose_query(prompt)
        if state.get("resolution"):
            decomposed.target_resolution = state["resolution"]  # type: ignore[assignment]
        return {"decomposed": decomposed, "step": "decompose_done"}
    except Exception as e:
        logger.error("Decomposition failed: %s", e, exc_info=True)
        return {"error": f"Decomposition failed: {e}", "step": "error"}


async def search_node(state: AgentState) -> dict[str, Any]:
    """Step 2: Hybrid search using decomposed queries."""
    logger.info("Step 2: Hybrid search")
    decomposed = state.get("decomposed")
    if decomposed is None:
        return {"error": "No decomposed query available", "step": "error"}

    queries = [sq.query for sq in decomposed.search_queries if sq.query]
    if not queries:
        queries = [state["prompt"][:100]]

    category = decomposed.category if decomposed.category != "unknown" else None

    try:
        results = multi_query_search(queries, category=category, limit=20)
        logger.info("Search returned %d results", len(results))
        return {"search_results": results, "step": "search_done"}
    except Exception as e:
        logger.warning("Search failed, continuing with empty results: %s", e)
        return {"search_results": [], "step": "search_done"}


async def rerank_node(state: AgentState) -> dict[str, Any]:
    """Step 3: Rerank search results for relevance."""
    logger.info("Step 3: Reranking")
    search_results = state.get("search_results", [])

    if not search_results:
        return {"ranked_results": [], "step": "rerank_done"}

    try:
        ranked = await rerank(state["prompt"], search_results, top_k=10)
        logger.info("Reranking produced %d results", len(ranked))
        return {"ranked_results": ranked, "step": "rerank_done"}
    except Exception as e:
        logger.warning("Reranking failed, using original order: %s", e)
        from src.rag.reranker import _fallback_ranking
        return {
            "ranked_results": _fallback_ranking(search_results, 10),
            "step": "rerank_done",
        }


async def build_prompt_node(state: AgentState) -> dict[str, Any]:
    """Step 4: Build generation prompt from decomposed query + references."""
    logger.info("Step 4: Prompt construction")
    decomposed = state.get("decomposed")
    ranked = state.get("ranked_results", [])

    if decomposed is None:
        return {"error": "No decomposed query for prompt building", "step": "error"}

    try:
        gen_prompt = await build_generation_prompt(decomposed, ranked)
        gen_prompt.reference_mode = state.get("reference_mode", "hybrid")
        return {"generation_prompt": gen_prompt, "step": "complete"}
    except Exception as e:
        logger.error("Prompt building failed: %s", e, exc_info=True)
        return {"error": f"Prompt building failed: {e}", "step": "error"}


def _should_continue(state: AgentState) -> str:
    if state.get("error"):
        return END
    step = state.get("step", "")
    step_map = {
        "decompose_done": "search",
        "search_done": "rerank",
        "rerank_done": "build_prompt",
        "complete": END,
    }
    return step_map.get(step, END)


def build_graph() -> StateGraph:
    """Build the LangGraph StateGraph for the RAG pipeline."""
    graph = StateGraph(AgentState)

    graph.add_node("decompose", decompose_node)
    graph.add_node("search", search_node)
    graph.add_node("rerank", rerank_node)
    graph.add_node("build_prompt", build_prompt_node)

    graph.set_entry_point("decompose")

    graph.add_conditional_edges("decompose", _should_continue)
    graph.add_conditional_edges("search", _should_continue)
    graph.add_conditional_edges("rerank", _should_continue)
    graph.add_conditional_edges("build_prompt", _should_continue)

    return graph


_compiled_graph = None


def get_compiled_graph() -> CompiledStateGraph:
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph().compile()
    return _compiled_graph


async def run_rag_pipeline(
    prompt: str,
    *,
    brand: str | None = None,
    reference_mode: str = "hybrid",
    resolution: dict[str, int] | None = None,
    style_reference_ids: list[str] | None = None,
    layout_reference_ids: list[str] | None = None,
) -> AgentState:
    """Execute the full RAG pipeline and return the final state."""
    graph = get_compiled_graph()

    initial_state: AgentState = {
        "prompt": prompt,
        "brand": brand,
        "reference_mode": reference_mode,
        "resolution": resolution,
        "style_reference_ids": style_reference_ids or [],
        "layout_reference_ids": layout_reference_ids or [],
    }

    result = await graph.ainvoke(initial_state)
    return result
