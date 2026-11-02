from __future__ import annotations

import difflib
import re

_DIGITS = re.compile(r"\d+")
URL_MATCH_CUTOFF = 0.97


def _resolve_reference(reference: str, source_type: str, tool_outputs: dict[str, str]) -> str | None:
    """Cari key `reference` di `tool_outputs`: modul toleran pada "block_id 85", oer toleran pada URL yang tertukar satu-dua karakter."""
    urls = [key for key in tool_outputs if key.startswith("http")]
    if source_type == "oer":
        if reference in urls:
            return reference
        close = difflib.get_close_matches(reference, urls, n=1, cutoff=URL_MATCH_CUTOFF) if reference.startswith("http") else []
        return close[0] if close else None
    if reference in tool_outputs and reference not in urls:
        return reference
    digits = _DIGITS.search(reference)
    return digits.group() if digits and digits.group() in tool_outputs and digits.group() not in urls else None


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
    needle_words = [w for w in _WORD.findall(_normalize(needle).lower()) if len(w) > 2 or w.isdigit()]
    haystack_words = set(w for w in _WORD.findall(_normalize(haystack).lower()) if len(w) > 2 or w.isdigit())
    if not needle_words:
        return False
    if any(w.isdigit() and w not in haystack_words for w in needle_words):
        return False
    matched = sum(1 for w in needle_words if w in haystack_words)
    return (matched / len(needle_words)) >= threshold


def verify_citations(sources: list[dict], tool_outputs: dict[str, str]) -> list[dict]:
    """`tool_outputs`: map reference -> konten mentah yang benar-benar dikembalikan tool (block
    text atau snippet OER). Setiap source ditandai `verified` -- kalau False,
    TETAP ditampilkan ke siswa (bukan disembunyikan) tapi dengan label eksplisit, supaya siswa/guru
    tahu ada ketidakpastian, bukan ilusi keakuratan."""
    verified = []
    for source in sources:
        key = _resolve_reference(source.get("reference", ""), source.get("source_type", ""), tool_outputs)
        checked = {**source, "verified": fuzzy_contains(source.get("evidence", ""), tool_outputs.get(key, ""))}
        if checked["verified"] and source.get("source_type") == "oer":
            checked["reference"] = key
        verified.append(checked)
    return verified
