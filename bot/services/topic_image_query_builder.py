from __future__ import annotations

import logging
import re

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


def _sanitize_query(value: str, max_len: int = 80) -> str:
    cleaned = re.sub(r"[\r\n\t]+", " ", value).strip().strip("\"'`")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip()
    return cleaned


async def build_photo_search_query_openrouter(
    *,
    topic: str,
    lang: str,
    openrouter_api_key: str,
    openrouter_models: tuple[str, ...],
    request_timeout_sec: int,
    max_model_attempts: int,
) -> str:
    raw_topic = topic.strip()
    if not raw_topic:
        return ""

    if not openrouter_api_key.strip() or not openrouter_models:
        return raw_topic

    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=openrouter_api_key.strip())
    timeout_sec = max(10, int(request_timeout_sec))
    models = openrouter_models[: max(1, int(max_model_attempts))]

    prompt = (
        "You create the best possible stock-photo search query for Pexels.\n"
        "Task:\n"
        "1) Read the topic.\n"
        "2) Return one precise search query 1-2 words that will produce highly relevant, realistic photos.\n\n"
        "Rules:\n"
        "- Return only one plain query line, no explanations.\n"
        "- Focus on the core visual concept, not abstract words.\n"
        "- Prefer concrete nouns/scenes suitable for photography.\n"
        "- Avoid brand names, quotation marks, punctuation spam, and hashtags.\n"
        "- Query language should match the input language.\n\n"
        f"Topic: {raw_topic}\n"
        f"Language code: {lang}"
    )

    for model in models:
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "Return one highly relevant stock-photo search query only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.15,
                timeout=timeout_sec,
            )
            candidate = _sanitize_query(response.choices[0].message.content or "")
            if candidate:
                return candidate
        except Exception as exc:
            logger.warning("Photo query generation failed (%s): %s", model, exc)

    return raw_topic

