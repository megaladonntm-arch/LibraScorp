from __future__ import annotations

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
    api_key = settings.openai_api_key.strip()
    if not api_key:
        raise ValueError("missing_openai_api_key")

    client = AsyncOpenAI(api_key=api_key)
    model = settings.openai_transcription_model.strip() or "gpt-4o-mini-transcribe"

    with voice_file_path.open("rb") as audio_file:
        transcript = await client.audio.transcriptions.create(
            model=model,
            file=audio_file,
            language=_effective_lang(lang),
            prompt=(
                "Transcribe this audio with high accuracy. Preserve meaning exactly, "
                "keep punctuation and speaker intent."
            ),
        )

    text = (transcript.text or "").strip()
    if not text:
        raise ValueError("empty_transcription")
    return text


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
