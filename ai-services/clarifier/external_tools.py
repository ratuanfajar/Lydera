from __future__ import annotations

import re

import httpx

from common import guardrails
from clarifier import config
from clarifier import trusted_domains

TIMEOUT = 15.0
_PRIVATE_USE = re.compile(r"[\ue000-\uf8ff]")
_SPACES = re.compile(r"[ \t\xa0]+")
NO_TRUSTED_SOURCE_NOTE = "Tidak ada sumber tepercaya yang cukup relevan untuk pertanyaan ini."


def search_oer(query: str) -> dict:
    """Cari di daftar host OER kurasi lewat search API; hasil di luar daftar atau berskor di bawah OER_MIN_SCORE dibuang."""
    if not config.SEARCH_API_KEY:
        return {"available": False, "results": [], "note": "SEARCH_API_KEY belum dikonfigurasi"}
    try:
        raw_results = fetch_results(query)
    except httpx.HTTPStatusError as exc:
        return {"available": False, "results": [], "note": f"Search API error {exc.response.status_code}"}
    except (httpx.HTTPError, httpx.InvalidURL, AttributeError, KeyError, TypeError, ValueError) as exc:
        return {"available": False, "results": [], "note": f"Search API error: {type(exc).__name__}"}

    results = [result for result in raw_results if _is_usable(result)]
    if not results:
        return {"available": True, "results": [], "note": NO_TRUSTED_SOURCE_NOTE}
    return {"available": True, "results": results}


def fetch_results(query: str) -> list[dict]:
    response = httpx.post(
        config.SEARCH_API_URL,
        headers={"Authorization": f"Bearer {config.SEARCH_API_KEY}"},
        json={
            "query": query,
            "include_domains": sorted(trusted_domains.OER_HOSTS),
            "max_results": 5,
            "search_depth": "advanced",
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return [
        {"url": item["url"], "title": item.get("title", ""), "snippet": _clean(item.get("content") or ""), "score": float(item.get("score") or 0.0)}
        for item in response.json().get("results", [])
    ]


def _is_usable(result: dict) -> bool:
    if guardrails.injection_markers(f"{result['title']} {result['snippet']}", strict=False):
        return False
    return bool(result["snippet"]) and trusted_domains.is_trusted(result["url"]) and result["score"] >= config.OER_MIN_SCORE


def _clean(text: str) -> str:
    return _SPACES.sub(" ", _PRIVATE_USE.sub(" ", text)).strip()
