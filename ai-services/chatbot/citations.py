"""Grounding check: pastikan `evidence` yang diklaim LLM benar-benar ada di konten yang
dikembalikan tool call, bukan kutipan karangan. Reuse semangat `quiz/validate.py` -- di sana
jawaban soal di-derive ulang independen lalu dibandingkan; di sini kutipan dicocokkan balik ke
sumber mentah, bukan dipercaya begitu saja dari output LLM."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

import trusted_domains

_DIGITS = re.compile(r"\d+")


def _lookup_raw_content(reference: str, tool_outputs: dict[str, str]) -> str:
    """Cari `reference` di `tool_outputs`. Model kadang nulis reference block modul dengan teks
    tambahan (mis. "block_id 85" alih-alih "85" polos) -- exact match dulu, kalau gagal coba
    angka yang terkandung di reference-nya (tool_outputs untuk modul selalu key-nya angka polos
    per chunk.py/sync_search.py). Bukan pelonggaran verifikasi, cuma toleransi format penulisan."""
    if reference in tool_outputs:
        return tool_outputs[reference]
    digits = _DIGITS.search(reference)
    if digits and digits.group() in tool_outputs:
        return tool_outputs[digits.group()]
    return ""


def fuzzy_contains(needle: str, haystack: str, threshold: float = 0.85) -> bool:
    """True kalau `needle` (evidence yang diklaim) cukup mirip salah satu potongan `haystack`
    (konten asli tool). Tidak butuh exact match karena LLM boleh merapikan spasi/tanda baca kecil,
    tapi tetap harus jelas berasal dari sana, bukan dikarang."""
    needle = needle.strip().lower()
    haystack = haystack.lower()
    if not needle:
        return False
    if needle in haystack:
        return True

    window = len(needle)
    step = max(1, window // 4)
    best = 0.0
    for start in range(0, max(1, len(haystack) - window + 1), step):
        chunk = haystack[start : start + window]
        best = max(best, SequenceMatcher(None, needle, chunk).ratio())
        if best >= threshold:
            return True
    return best >= threshold


def verify_citations(sources: list[dict], tool_outputs: dict[str, str]) -> list[dict]:
    """`tool_outputs`: map reference -> konten mentah yang benar-benar dikembalikan tool (block
    text, snippet OER/web, atau hasil Wolfram). Setiap source ditandai `verified` -- kalau False,
    TETAP ditampilkan ke siswa (bukan disembunyikan) tapi dengan label eksplisit, supaya siswa/guru
    tahu ada ketidakpastian, bukan ilusi keakuratan."""
    verified = []
    for source in sources:
        raw_content = _lookup_raw_content(source.get("reference", ""), tool_outputs)
        source = {**source, "verified": fuzzy_contains(source.get("evidence", ""), raw_content)}

        # trust_tier DIHITUNG ULANG dari reference (URL), bukan dipercaya dari isian model --
        # model sering lupa/salah nyalin nilai yang sebenarnya sudah kita hitung sendiri di
        # trusted_domains.py saat tool dipanggil.
        if source.get("source_type") in ("web", "oer"):
            source["trust_tier"] = trusted_domains.trust_tier(source.get("reference", ""))
        elif source.get("source_type") == "modul":
            source["trust_tier"] = None
        # wolfram_alpha: biarkan apa adanya (bukan link, tidak relevan trust_tier domain)

        verified.append(source)
    return verified
