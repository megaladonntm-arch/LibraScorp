from __future__ import annotations

import base64
import logging
from pathlib import Path

from openai import AsyncOpenAI

from bot.config import load_settings

logger = logging.getLogger(__name__)
settings = load_settings()


def _effective_lang(lang: str | None) -> str | None:
    if lang in {"ru", "en", "uz"}:
        return lang
    return None


async def transcribe_voice_file(voice_file_path: Path, lang: str | None = None) -> str:
    api_key = settings.openrouter_api_key.strip()
    if not api_key:
        raise ValueError("missing_openrouter_api_key")

    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    models = settings.openrouter_models[: max(1, int(settings.openrouter_max_model_attempts))]
    if not models:
        raise ValueError("missing_openrouter_models")

    audio_b64 = base64.b64encode(voice_file_path.read_bytes()).decode("ascii")
    language_name = {"ru": "Russian", "en": "English", "uz": "Uzbek"}.get(lang or "", "Russian")

    last_error: Exception | None = None
    for model in models:
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a speech-to-text engine. "
                            "Return only the transcript text, without comments."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Transcribe this voice message very accurately. "
                                    f"Primary language: {language_name}. "
                                    "Keep punctuation and proper names."
                                ),
                            },
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": audio_b64,
                                    "format": "ogg",
                                },
                            },
                        ],
                    },
                ],
                temperature=0,
                timeout=max(10, int(settings.openrouter_request_timeout_sec)),
            )

            content = response.choices[0].message.content
            if isinstance(content, str):
                text = content.strip()
            elif isinstance(content, list):
                parts: list[str] = []
                for item in content:
                    if isinstance(item, dict) and isinstance(item.get("text"), str):
                        parts.append(item["text"].strip())
                text = "\n".join(part for part in parts if part).strip()
            else:
                text = ""

            if text:
                return text
        except Exception as exc:
            last_error = exc
            logger.warning("OpenRouter transcription model failed (%s): %s", model, exc)

    if last_error is not None:
        raise last_error
    raise ValueError("empty_transcription")


async def ask_openrouter_from_text(user_text: str, lang: str = "ru") -> str:
    api_key = settings.openrouter_api_key.strip()
    if not api_key:
        raise ValueError("missing_openrouter_api_key")

    timeout_sec = max(10, int(settings.openrouter_request_timeout_sec))
    max_attempts = max(1, int(settings.openrouter_max_model_attempts))
    models = settings.openrouter_models[:max_attempts]
    if not models:
        raise ValueError("missing_openrouter_models")

    language_name = {"ru": "Russian", "en": "English", "uz": "Uzbek"}.get(lang, "Russian")
    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    last_error: Exception | None = None
    for model in models:
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a precise, practical assistant. "
                            f"Answer in {language_name} unless the user asks another language."
                        ),
                    },
                    {"role": "user", "content": user_text[:12000]},
                ],
                temperature=0.3,
                timeout=timeout_sec,
            )
            answer = (response.choices[0].message.content or "").strip()
            if answer:
                return answer
        except Exception as exc:
            last_error = exc
            logger.warning("OpenRouter chat model failed (%s): %s", model, exc)

    if last_error is not None:
        raise last_error
    raise ValueError("empty_openrouter_response")
