from __future__ import annotations

import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

MAX_SOURCE_CHARS = 12000
MAX_DOWNLOAD_BYTES = 2_000_000
SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".log"}


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        stripped = data.strip()
        if stripped:
            self._chunks.append(stripped)

    def text(self) -> str:
        return " ".join(self._chunks)


def normalize_source_text(text: str, max_chars: int = MAX_SOURCE_CHARS) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned[:max_chars]


def is_http_url(value: str) -> bool:
    return bool(re.match(r"^https?://", value.strip(), flags=re.IGNORECASE))


def _decode_bytes(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1251", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("failed_to_decode")

#extract encodeing and chking file prototype for manager
def extract_text_from_file(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_TEXT_EXTENSIONS:
        raise ValueError("unsupported_file_type")
    content = file_path.read_bytes()
    if len(content) > MAX_DOWNLOAD_BYTES:
        raise ValueError("file_too_large")
    return normalize_source_text(_decode_bytes(content))


def extract_text_from_url(url: str) -> str:
    req = urllib.request.Request(
        url=url.strip(),
        headers={"User-Agent": "Mozilla/5.0 (compatible; presentation-bot/1.0)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            payload = resp.read(MAX_DOWNLOAD_BYTES + 1)
            if len(payload) > MAX_DOWNLOAD_BYTES:
                raise ValueError("url_too_large")
            content_type = (resp.headers.get("Content-Type") or "").lower()
    except urllib.error.URLError as exc:
        raise ValueError("url_fetch_failed") from exc

    raw = _decode_bytes(payload)
    if "text/html" in content_type:
        parser = _HTMLTextExtractor()
        parser.feed(raw)
        extracted = parser.text()
        return normalize_source_text(extracted)
    return normalize_source_text(raw)


    
