"""Build generation prompts from decomposed query and reference images."""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from src.rag.decomposer import DecomposedQuery
from src.rag.llm import chat_text
from src.rag.reranker import RankedResult

logger = logging.getLogger(__name__)


class GenerationPrompt(BaseModel):
    """Structured prompt for the image generation engine (ComfyUI)."""

    positive_prompt: str = ""
    negative_prompt: str = "blurry, low quality, distorted, watermark, text artifacts"
    style_prompt: str = ""
    reference_ids: list[str] = Field(default_factory=list)
    reference_mode: str = "hybrid"
    resolution: dict[str, int] = Field(
        default_factory=lambda: {"width": 1920, "height": 1080}
    )
    category: str = "unknown"
    color_palette: list[str] = Field(default_factory=list)
    layout_type: str = "freeform"
    metadata: dict = Field(default_factory=dict)


SYSTEM_PROMPT = """\
You are an expert at crafting image generation prompts. Given a structured design request \
and reference image information, produce a high-quality positive prompt for a diffusion model.

The prompt should:
- Be detailed and descriptive (50-150 words)
- Include style, mood, color, composition, and technical details
- Reference specific design elements from the user request
- Incorporate insights from the reference images when available
- Be in English regardless of input language

Also produce:
- A negative prompt (things to avoid)
- A style-specific prompt fragment

Respond as plain text in this exact format:
POSITIVE: <positive prompt>
NEGATIVE: <negative prompt>
STYLE: <style prompt>
"""


async def build_generation_prompt(
    decomposed: DecomposedQuery,
    references: list[RankedResult],
) -> GenerationPrompt:
    """
    Build a structured generation prompt from decomposed query and ranked references.
    Falls back to rule-based construction if LLM is unavailable.
    """
    ref_descriptions = _format_references(references)
    user_prompt = (
        f"Design request:\n"
        f"- Category: {decomposed.category}\n"
        f"- Style: {', '.join(decomposed.style_keywords)}\n"
        f"- Mood: {decomposed.mood}\n"
        f"- Colors: {', '.join(decomposed.color_palette)}\n"
        f"- Layout: {decomposed.layout_type}\n"
        f"- Text content: {decomposed.text_content or 'none'}\n\n"
        f"Reference images:\n{ref_descriptions or 'No references found'}"
    )

    llm_response = await chat_text(SYSTEM_PROMPT, user_prompt)

    if llm_response:
        return _parse_llm_response(llm_response, decomposed, references)

    return _rule_based_prompt(decomposed, references)


def _parse_llm_response(
    response: str,
    decomposed: DecomposedQuery,
    references: list[RankedResult],
) -> GenerationPrompt:
    positive = ""
    negative = "blurry, low quality, distorted, watermark"
    style = ""

    for line in response.strip().split("\n"):
        line = line.strip()
        if line.startswith("POSITIVE:"):
            positive = line[len("POSITIVE:"):].strip()
        elif line.startswith("NEGATIVE:"):
            negative = line[len("NEGATIVE:"):].strip()
        elif line.startswith("STYLE:"):
            style = line[len("STYLE:"):].strip()

    if not positive:
        positive = response[:500]

    return GenerationPrompt(
        positive_prompt=positive,
        negative_prompt=negative,
        style_prompt=style,
        reference_ids=[r.id for r in references],
        resolution=decomposed.target_resolution,
        category=decomposed.category,
        color_palette=decomposed.color_palette,
        layout_type=decomposed.layout_type,
        metadata={"source": "llm", "mood": decomposed.mood},
    )


def _rule_based_prompt(
    decomposed: DecomposedQuery,
    references: list[RankedResult],
) -> GenerationPrompt:
    """Construct prompt from extracted elements without LLM."""
    parts = []

    if decomposed.category != "unknown":
        parts.append(f"A {decomposed.category} design")

    if decomposed.style_keywords:
        parts.append(f"in {', '.join(decomposed.style_keywords)} style")

    if decomposed.mood:
        parts.append(f"with a {decomposed.mood} mood")

    if decomposed.color_palette:
        colors = ", ".join(decomposed.color_palette[:4])
        parts.append(f"using colors {colors}")

    if decomposed.layout_type != "freeform":
        parts.append(f"with {decomposed.layout_type} layout")

    if decomposed.text_content:
        parts.append(f'featuring text "{decomposed.text_content}"')

    parts.append("high quality, professional, 4K, sharp details")

    positive = ", ".join(parts) if parts else "modern design, high quality"

    negative_parts = list(decomposed.negative_keywords) if decomposed.negative_keywords else []
    negative_parts.extend(["blurry", "low quality", "distorted", "watermark"])
    negative = ", ".join(dict.fromkeys(negative_parts))

    style_parts = decomposed.style_keywords[:3] + [decomposed.mood]
    style = ", ".join(s for s in style_parts if s)

    return GenerationPrompt(
        positive_prompt=positive,
        negative_prompt=negative,
        style_prompt=style,
        reference_ids=[r.id for r in references],
        resolution=decomposed.target_resolution,
        category=decomposed.category,
        color_palette=decomposed.color_palette,
        layout_type=decomposed.layout_type,
        metadata={"source": "rule_based", "mood": decomposed.mood},
    )


def _format_references(references: list[RankedResult]) -> str:
    if not references:
        return ""
    lines = []
    for i, ref in enumerate(references[:5], 1):
        caption = ref.payload.get("caption", "")
        category = ref.payload.get("category", "")
        tags = ", ".join(ref.payload.get("style_tags", []))
        lines.append(
            f"{i}. [{category}] {caption} (tags: {tags}, relevance: {ref.score:.2f})"
        )
    return "\n".join(lines)
