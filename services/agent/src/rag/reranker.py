"""Reranking module: score search candidates for relevance using GPT-5.4."""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from src.rag.llm import chat_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a design relevance expert. Given a user's design request and a list of candidate \
reference images (with metadata), score each candidate from 0.0 to 1.0 based on relevance.

Consider:
- How well the candidate's style matches the request
- Category relevance
- Caption/description alignment with the user's intent

Respond in JSON:
{
  "rankings": [
    {"id": "candidate-id", "score": 0.95, "reason": "brief reason"},
    ...
  ]
}

Return ALL candidates with updated scores. Order by score descending.
"""


class RankedResult(BaseModel):
    id: str
    score: float
    reason: str = ""
    payload: dict = Field(default_factory=dict)


async def rerank(
    query: str,
    candidates: list[tuple[str, float, dict]],
    *,
    top_k: int = 10,
) -> list[RankedResult]:
    """
    Rerank search candidates using GPT-5.4.
    Falls back to original score ordering if API key is not set.
    """
    if not candidates:
        return []

    candidate_descriptions = []
    for id_, score, payload in candidates[:20]:
        candidate_descriptions.append({
            "id": str(id_),
            "original_score": round(score, 4),
            "category": payload.get("category", "unknown"),
            "caption": payload.get("caption", ""),
            "style_tags": payload.get("style_tags", []),
        })

    user_prompt = (
        f"User request: {query}\n\n"
        f"Candidates:\n{_format_candidates(candidate_descriptions)}"
    )

    data = await chat_json(SYSTEM_PROMPT, user_prompt)

    if not data or "rankings" not in data:
        logger.info("Using original scores (no LLM reranking)")
        return _fallback_ranking(candidates, top_k)

    id_to_payload = {str(id_): payload for id_, _, payload in candidates}
    results = []
    for item in data["rankings"]:
        cid = item.get("id", "")
        if cid in id_to_payload:
            results.append(
                RankedResult(
                    id=cid,
                    score=float(item.get("score", 0.0)),
                    reason=item.get("reason", ""),
                    payload=id_to_payload[cid],
                )
            )

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_k]


def _fallback_ranking(
    candidates: list[tuple[str, float, dict]],
    top_k: int,
) -> list[RankedResult]:
    """Use original vector search scores when LLM is unavailable."""
    sorted_candidates = sorted(candidates, key=lambda x: x[1], reverse=True)
    return [
        RankedResult(id=str(id_), score=score, payload=payload)
        for id_, score, payload in sorted_candidates[:top_k]
    ]


def _format_candidates(candidates: list[dict]) -> str:
    lines = []
    for i, c in enumerate(candidates, 1):
        tags = ", ".join(c.get("style_tags", []))
        lines.append(
            f"{i}. id={c['id']} category={c['category']} "
            f"tags=[{tags}] caption=\"{c['caption']}\" "
            f"score={c['original_score']}"
        )
    return "\n".join(lines)
