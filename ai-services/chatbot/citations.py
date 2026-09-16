"""Grounding check: pastikan `evidence` yang diklaim LLM benar-benar ada di konten yang
dikembalikan tool call, bukan kutipan karangan. Reuse semangat `quiz/validate.py` -- di sana
jawaban soal di-derive ulang independen lalu dibandingkan; di sini kutipan dicocokkan balik ke
sumber mentah, bukan dipercaya begitu saja dari output LLM."""

from __future__ import annotations

import re

from chatbot import trusted_domains

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


_WHITESPACE = re.compile(r"\s+")
_LEADING_NUMBERING = re.compile(r"^(?:\d+|[ivxIVX]+|[a-zA-Z])[.)]\s*")
_WORD = re.compile(r"\w+")


def _normalize(text: str) -> str:
    """Konten mentah dari PDF/OCR penuh `\\n\\n` dan penomoran ("1. ", "I. ") -- LLM WAJAR
    merapikannya jadi kalimat mengalir biasa saat mengutip (mis. ganti newline jadi ": "). Itu
    bukan tanda kutipan dikarang, cuma beda representasi whitespace/format. Disamakan dulu sebelum
    dibandingkan, supaya perbandingan tidak jatuh gara-gara ini -- bukan pelonggaran syarat konten,
    cuma menghilangkan noise format yang tidak relevan ke isi."""
    text = _LEADING_NUMBERING.sub("", text.strip())
    text = _WHITESPACE.sub(" ", text)
    return text.strip()


def fuzzy_contains(needle: str, haystack: str, threshold: float = 0.75) -> bool:
    """True kalau kata-kata di `needle` (evidence yang diklaim) sebagian besar (>= threshold)
    beneran ada di `haystack` (konten asli tool). Dipilih overlap KATA, bukan kemiripan karakter
    berurutan (`SequenceMatcher`) -- LLM WAJAR meringkas/menggabungkan beberapa kalimat sumber jadi
    satu kalimat kutipan (buang kata sambung, satukan 2 poin jadi 1), yang mengubah urutan/struktur
    karakter cukup jauh walau isinya identik. Overlap kata tetap ketat soal ISI (kata yang tidak
    pernah ada di sumber = jelas dikarang, langsung menjatuhkan skor), tapi tidak peduli urutan/
    penggabungan kalimat."""
    needle_words = [w for w in _WORD.findall(_normalize(needle).lower()) if len(w) > 2]
    haystack_words = set(w for w in _WORD.findall(_normalize(haystack).lower()) if len(w) > 2)
    if not needle_words:
        return False
    matched = sum(1 for w in needle_words if w in haystack_words)
    return (matched / len(needle_words)) >= threshold


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
