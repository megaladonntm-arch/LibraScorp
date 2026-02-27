from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from bot.services.source_extractor import normalize_source_text

WIKIPEDIA_API_URL = "https://ru.wikipedia.org/w/api.php"
DEFAULT_TIMEOUT_SEC = 12
DEFAULT_MAX_CHARS = 12000
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WikipediaLookupResult:
    requested_topic: str
    resolved_title: str
    page_url: str
    text: str


def _request_json(params: dict[str, str], timeout_sec: int) -> dict:
    query = urlencode(params)
    request = Request(
        f"{WIKIPEDIA_API_URL}?{query}",
        headers={"User-Agent": "LibraScorpBot/1.0 (wikipedia-source)"},
        method="GET",
    )
    with urlopen(request, timeout=max(5, timeout_sec)) as response:
        payload = response.read().decode("utf-8")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("invalid_wikipedia_payload")
    return data


def _search_best_title(topic: str, timeout_sec: int) -> str | None:
    data = _request_json(
        {
            "action": "query",
            "format": "json",
            "utf8": "1",
            "list": "search",
            "srsearch": topic,
            "srlimit": "1",
        },
        timeout_sec=timeout_sec,
    )
    query = data.get("query")
    if not isinstance(query, dict):
        return None
    search = query.get("search")
    if not isinstance(search, list) or not search:
        return None
    first = search[0]
    if not isinstance(first, dict):
        return None
    title = first.get("title")
    if not isinstance(title, str):
        return None
    cleaned = title.strip()
    return cleaned or None


def _extract_page_text(title: str, timeout_sec: int, max_chars: int) -> str:
    data = _request_json(
        {
            "action": "query",
            "format": "json",
            "utf8": "1",
            "redirects": "1",
            "prop": "extracts",
            "explaintext": "1",
            "exchars": str(max(1000, max_chars)),
            "titles": title,
        },
        timeout_sec=timeout_sec,
    )
    query = data.get("query")
    if not isinstance(query, dict):
        return ""
    pages = query.get("pages")
    if not isinstance(pages, dict):
        return ""
    for page in pages.values():
        if not isinstance(page, dict):
            continue
        extract = page.get("extract")
        if isinstance(extract, str) and extract.strip():
            return extract
    return ""


def _fetch_wikipedia_source_sync(topic: str, timeout_sec: int, max_chars: int) -> WikipediaLookupResult | None:
    normalized_topic = topic.strip()
    if not normalized_topic:
        return None

    exact_text = _extract_page_text(normalized_topic, timeout_sec=timeout_sec, max_chars=max_chars)
    normalized_exact = normalize_source_text(exact_text, max_chars=max_chars)
    if normalized_exact:
        exact_url = f"https://ru.wikipedia.org/wiki/{quote(normalized_topic.replace(' ', '_'))}"
        return WikipediaLookupResult(
            requested_topic=normalized_topic,
            resolved_title=normalized_topic,
            page_url=exact_url,
            text=normalized_exact,
        )

    title = _search_best_title(normalized_topic, timeout_sec=timeout_sec)
    if not title:
        return None

    extracted = _extract_page_text(title, timeout_sec=timeout_sec, max_chars=max_chars)
    normalized_text = normalize_source_text(extracted, max_chars=max_chars)
    if not normalized_text:
        return None

    page_url = f"https://ru.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
    return WikipediaLookupResult(
        requested_topic=normalized_topic,
        resolved_title=title,
        page_url=page_url,
        text=normalized_text,
    )


async def fetch_russian_wikipedia_source(
    topic: str,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> WikipediaLookupResult | None:
    try:
        return await asyncio.to_thread(
            _fetch_wikipedia_source_sync,
            topic,
            max(5, timeout_sec),
            max(1000, max_chars),
        )
    except Exception as exc:
        logger.warning("Failed to fetch Russian Wikipedia source for topic '%s': %s", topic, exc)
        return None
