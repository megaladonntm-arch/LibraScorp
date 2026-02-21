from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from faster_whisper import WhisperModel
from openai import AsyncOpenAI

from bot.config import load_settings

logger = logging.getLogger(__name__)
settings = load_settings()
_whisper_model: WhisperModel | None = None


def _effective_lang(lang: str | None) -> str | None:
    if lang in {"ru", "en", "uz"}:
        return lang
    return None


def _get_whisper_model() -> WhisperModel:
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = WhisperModel(
            settings.whisper_model_size,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
    return _whisper_model


def _transcribe_sync(voice_file_path: Path, lang: str | None = None) -> str:
    model = _get_whisper_model()
    segments, _ = model.transcribe(
        str(voice_file_path),
        language=_effective_lang(lang),
        vad_filter=True,
        beam_size=5,
        best_of=5,
    )
    text = " ".join(segment.text.strip() for segment in segments if segment.text).strip()
    if not text:
        raise ValueError("empty_transcription")
    return text


async def transcribe_voice_file(voice_file_path: Path, lang: str | None = None) -> str:
    return await asyncio.to_thread(_transcribe_sync, voice_file_path, lang)


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
