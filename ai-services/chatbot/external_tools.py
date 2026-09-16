"""Implementasi tool eksternal: Wolfram Alpha (Full Results API, tier gratis), OER search, dan
web search akademik (domain-filtered). Semua panggil HTTP murni, tidak menyentuh DB -- konsisten
dengan aturan ai-services/CONTRACT.md."""

from __future__ import annotations

import httpx

from annotation import cache
from annotation import config
from chatbot import trusted_domains

TIMEOUT = 15.0

# Katalog OER yang di-support langsung (dicari lewat masing-masing scoping-nya, bukan search engine
# generik) -- lihat trusted_domains.TIER2_DOMAINS untuk daftar domain yang diizinkan tampil ke siswa.
_OER_SITES = " OR ".join(f"site:{d}" for d in sorted(trusted_domains.TIER2_DOMAINS))


def query_wolfram_alpha(query: str) -> dict:
    """Full Results API (masih tier gratis -- 2000 call/bulan, non-komersial). Beda dari Short
    Answers: response-nya berstruktur "pods" (Input, Result, Plot, dst), bukan satu baris teks --
    jadi diambil pod yang paling relevan (`_extract_answer`), bukan seluruh isinya, supaya tetap
    dipakai sebagai cross-check singkat, bukan sumber penjelasan panjang (step-by-step solution
    tidak termasuk tier gratis ini). Di-cache lama (fakta matematis tidak berubah) dan kuota tier
    gratis terbatas per bulan."""
    if not config.WOLFRAM_APP_ID:
        return {"available": False, "answer": None, "note": "WOLFRAM_APP_ID belum dikonfigurasi"}

    cached = cache.get("wolfram_full_result", query)
    if cached is not None:
        return {"available": True, "answer": cached, "cached": True}

    try:
        response = httpx.get(
            config.WOLFRAM_API_URL,
            params={
                "appid": config.WOLFRAM_APP_ID,
                "input": query,
                "format": "plaintext",
                "output": "JSON",
                "units": "metric",
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json().get("queryresult", {})
    except httpx.HTTPError as exc:
        return {"available": False, "answer": None, "note": f"Wolfram Alpha error: {exc}"}

    if not data.get("success"):
        return {"available": True, "answer": None, "note": "Wolfram Alpha tidak menemukan jawaban"}

    answer = _extract_answer(data.get("pods", []))
    if answer is None:
        return {"available": True, "answer": None, "note": "Tidak ada pod hasil yang bisa diambil"}

    cache.put("wolfram_full_result", answer, query)
    return {"available": True, "answer": answer, "cached": False}


_PREFERRED_POD_TITLES = {"result", "results", "value", "decimal approximation", "solution", "derivative"}


def _extract_answer(pods: list[dict]) -> str | None:
    """Ambil pod yang paling relevan buat cross-check singkat -- prioritas pod bertitle "Result"
    dkk, fallback pod pertama yang bukan "Input" kalau tidak ada yang cocok."""
    def plaintext_of(pod: dict) -> str:
        return "; ".join(s.get("plaintext", "") for s in pod.get("subpods", []) if s.get("plaintext"))

    for pod in pods:
        if pod.get("title", "").lower() in _PREFERRED_POD_TITLES:
            text = plaintext_of(pod)
            if text:
                return text

    for pod in pods:
        if pod.get("id") != "Input" and pod.get("title", "").lower() != "input":
            text = plaintext_of(pod)
            if text:
                return text

    return None


def search_oer(query: str, subject: str = "") -> dict:
    """Cari di katalog OER yang sudah dikurasi (tier 2), lewat search API yang sama tapi
    scope-nya dibatasi ke domain OER saja (bukan web umum)."""
    full_query = f"{query} {subject} ({_OER_SITES})".strip()
    return _run_search(full_query, restrict_to_tier2=True)


def search_academic_web(query: str) -> dict:
    """Web search umum -- semua hasil ditampilkan (tidak dibuang), tapi diberi label `trust_tier`
    dan diurutkan: .edu/.gov/arxiv (tier 1) paling diutamakan, lalu OER (tier 2), sisanya termasuk
    Wikipedia/blog di tier 3 (paling rendah, ditandai jelas -- lihat trusted_domains.py). Ini LAST
    RESORT -- dipanggil kalau modul dan OER tidak punya jawabannya."""
    return _run_search(query, restrict_to_tier2=False)


def _run_search(query: str, restrict_to_tier2: bool) -> dict:
    if not config.SEARCH_API_KEY:
        return {"available": False, "results": [], "note": "SEARCH_API_KEY belum dikonfigurasi"}

    try:
        response = httpx.post(
            config.SEARCH_API_URL,
            headers={"Authorization": f"Bearer {config.SEARCH_API_KEY}"},
            json={
                "query": query,
                # enforcement di level API call (bukan cuma post-filter) -- lihat include_domains
                # untuk provider yang mendukungnya (mis. Tavily).
                "include_domains": sorted(trusted_domains.TIER2_DOMAINS) if restrict_to_tier2 else [],
                "max_results": 5,
                # "advanced" -- konten lebih lengkap dari sekadar preview singkat, supaya model
                # punya cukup bahan buat MENGUTIP beneran, bukan menulis ulang dari ingatannya
                # sendiri (yang gagal lolos verify_citations meski faktanya kebetulan benar).
                "search_depth": "advanced",
            },
            timeout=TIMEOUT,
        )
        if response.status_code >= 400:
            return {
                "available": False,
                "results": [],
                "note": f"Search API error {response.status_code}: {response.text[:300]}",
            }
        raw_results = response.json().get("results", [])
    except httpx.HTTPError as exc:
        return {"available": False, "results": [], "note": f"Search API error: {exc}"}

    # Tidak ada yang dibuang -- semua hasil diberi trust_tier dan diurutkan (.edu/.gov/arxiv dulu),
    # supaya model (dan siswa) tahu mana yang paling terpercaya tanpa kehilangan hasil yang
    # sebenarnya relevan tapi domainnya bukan akademik formal (Wikipedia, blog, dst -- tier 3).
    normalized = [{"url": r["url"], "title": r.get("title", ""), "snippet": r.get("content", "")} for r in raw_results]
    ranked = trusted_domains.rank_results(normalized)

    if not ranked:
        return {"available": True, "results": [], "note": "Tidak ada hasil ditemukan"}
    return {"available": True, "results": ranked}
