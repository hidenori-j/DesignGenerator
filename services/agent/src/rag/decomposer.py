"""Query decomposition: extract design elements from user prompt via GPT-5.4."""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from src.rag.llm import chat_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a design analysis expert. Given a user's design request, extract structured design elements.
Respond in JSON with the following schema:

{
  "category": "banner | ui | icon | illustration | web_design | poster | unknown",
  "style_keywords": ["keyword1", "keyword2"],
  "color_palette": ["#hex1", "#hex2"],
  "layout_type": "centered | grid | split | hero | card | freeform",
  "text_content": "any text that should appear in the design",
  "mood": "minimal | bold | elegant | playful | corporate | futuristic",
  "search_queries": [
    {"purpose": "style", "query": "search query for style reference"},
    {"purpose": "layout", "query": "search query for layout reference"}
  ],
  "negative_keywords": ["things to avoid"],
  "target_resolution": {"width": 1920, "height": 1080}
}

Rules:
- search_queries should contain 2-4 diverse queries to find good reference images
- style_keywords should be concise visual descriptors
- If the prompt is in Japanese, still extract English keywords for search
- If information is not specified, use reasonable defaults
"""


class SearchQuery(BaseModel):
    purpose: str = "style"
    query: str = ""


class DecomposedQuery(BaseModel):
    category: str = "unknown"
    style_keywords: list[str] = Field(default_factory=list)
    color_palette: list[str] = Field(default_factory=list)
    layout_type: str = "freeform"
    text_content: str = ""
    mood: str = "minimal"
    search_queries: list[SearchQuery] = Field(default_factory=list)
    negative_keywords: list[str] = Field(default_factory=list)
    target_resolution: dict[str, int] = Field(
        default_factory=lambda: {"width": 1920, "height": 1080}
    )


def _mock_decomposition(prompt: str) -> DecomposedQuery:
    """Fallback when OpenAI API key is not configured."""
    words = prompt.lower().split()
    style = [w for w in words if len(w) > 3][:5]
    return DecomposedQuery(
        category="web_design",
        style_keywords=style or ["modern", "clean"],
        color_palette=["#1a1a2e", "#16213e", "#0f3460", "#e94560"],
        layout_type="centered",
        text_content="",
        mood="minimal",
        search_queries=[
            SearchQuery(purpose="style", query=prompt[:80]),
            SearchQuery(purpose="layout", query=f"layout {prompt[:60]}"),
        ],
        negative_keywords=["blurry", "low quality"],
    )


async def decompose_query(prompt: str) -> DecomposedQuery:
    """Decompose a user prompt into structured design elements."""
    data = await chat_json(SYSTEM_PROMPT, prompt)

    if not data:
        logger.info("Using mock decomposition (no API key or LLM failure)")
        return _mock_decomposition(prompt)

    search_queries = [
        SearchQuery(purpose=sq.get("purpose", "style"), query=sq.get("query", ""))
        for sq in data.get("search_queries", [])
    ]
    if not search_queries:
        search_queries = [SearchQuery(purpose="style", query=prompt[:80])]

    return DecomposedQuery(
        category=data.get("category", "unknown"),
        style_keywords=data.get("style_keywords", []),
        color_palette=data.get("color_palette", []),
        layout_type=data.get("layout_type", "freeform"),
        text_content=data.get("text_content", ""),
        mood=data.get("mood", "minimal"),
        search_queries=search_queries,
        negative_keywords=data.get("negative_keywords", []),
        target_resolution=data.get("target_resolution", {"width": 1920, "height": 1080}),
    )
