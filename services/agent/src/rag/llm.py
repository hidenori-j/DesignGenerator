"""OpenAI client utilities with JSON mode and mock fallback."""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from src.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _is_configured() -> bool:
    return bool(settings.openai_api_key)


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def chat_json(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> dict[str, Any]:
    """
    Call GPT with JSON response format.
    Falls back to empty dict if API key is not set.
    """
    if not _is_configured():
        logger.warning("OPENAI_API_KEY not set, returning empty response")
        return {}

    client = get_client()
    try:
        response = await client.chat.completions.create(
            model=model or settings.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON from LLM response")
        return {}
    except Exception:
        logger.error("LLM call failed", exc_info=True)
        return {}


async def chat_text(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """Call GPT for plain text response. Returns empty string on failure."""
    if not _is_configured():
        logger.warning("OPENAI_API_KEY not set, returning empty response")
        return ""

    client = get_client()
    try:
        response = await client.chat.completions.create(
            model=model or settings.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
    except Exception:
        logger.error("LLM call failed", exc_info=True)
        return ""
