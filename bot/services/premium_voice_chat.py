from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path

from openai import AsyncOpenAI
from pydub import AudioSegment
import speech_recognition as sr

from bot.config import load_settings

logger = logging.getLogger(__name__)
settings = load_settings()


def _effective_lang(lang: str | None) -> str | None:
    mapping = {
        "ru": "ru-RU",
        "en": "en-US",
        "uz": "uz-UZ",
    }
    return mapping.get(lang or "", "ru-RU")


@lru_cache(maxsize=1)
def _resolve_ffmpeg_binary() -> str | None:
    # Prefer explicit env override, then system ffmpeg, then bundled binary from imageio-ffmpeg.
    for env_name in ("FFMPEG_PATH", "FFMPEG_BINARY"):
        candidate = os.getenv(env_name, "").strip()
        if candidate and Path(candidate).exists():
            return candidate

    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    try:
        import imageio_ffmpeg

        binary = imageio_ffmpeg.get_ffmpeg_exe()
        if binary and Path(binary).exists():
            return binary
    except Exception:
        logger.exception("Failed to resolve ffmpeg with imageio-ffmpeg")

    return None


def _decode_ogg_to_wav(ogg_path: Path, wav_path: Path) -> None:
    ffmpeg_binary = _resolve_ffmpeg_binary()
    if not ffmpeg_binary:
        raise RuntimeError("ffmpeg_not_found")

    AudioSegment.converter = ffmpeg_binary
    AudioSegment.ffmpeg = ffmpeg_binary

    audio = AudioSegment.from_file(str(ogg_path), format="ogg")
    if len(audio) <= 0:
        raise ValueError("empty_audio")

    # Normalize for SpeechRecognition: mono, 16 kHz, 16-bit PCM.
    normalized = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
    normalized.export(str(wav_path), format="wav")


def _transcribe_sync(voice_file_path: Path, lang: str | None = None) -> str:
    recognizer = sr.Recognizer()
    with tempfile.TemporaryDirectory(prefix="voice_wav_") as temp_dir:
        wav_path = Path(temp_dir) / "voice.wav"
        _decode_ogg_to_wav(voice_file_path, wav_path)
        with sr.AudioFile(str(wav_path)) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio, language=_effective_lang(lang)).strip()
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
