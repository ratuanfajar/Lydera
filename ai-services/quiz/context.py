import cache
import config
import llm

SEGMENT_SYSTEM = (
    "Anda meringkas satu bagian dari buku matematika SMA. Tulis 1-2 kalimat ringkas dalam Bahasa "
    "Indonesia yang menjelaskan bagian ini membahas apa. Keluarkan hanya ringkasannya, tanpa "
    "kalimat pembuka."
)

CHAPTER_SYSTEM = (
    "Anda merangkum satu bab buku matematika SMA dari kumpulan ringkasan tiap bagiannya. Gabungkan "
    "menjadi satu paragraf ringkas dalam Bahasa Indonesia yang menjelaskan topik-topik yang dibahas "
    "bab ini secara keseluruhan. Keluarkan hanya ringkasannya, tanpa kalimat pembuka."
)


def summarize_segment(segment) -> str:
    """Chain 1 (map): ringkas satu segmen jadi 1-2 kalimat, memakai cache."""
    cached = cache.get("quiz_segment_summary", segment.text, config.QUIZ_MODEL, config.PROMPT_VERSION)
    if cached is not None:
        return cached
    result = llm.complete_text(SEGMENT_SYSTEM, segment.text, model=config.QUIZ_MODEL)
    cache.put("quiz_segment_summary", result, segment.text, config.QUIZ_MODEL, config.PROMPT_VERSION)
    return result


def summarize_chapter(segment_summaries: list[str]) -> str:
    """Chain 2 (reduce): gabungkan semua ringkasan segmen satu bab jadi satu ringkasan bab, memakai cache."""
    combined = "\n".join(segment_summaries)
    cached = cache.get("quiz_chapter_summary", combined, config.QUIZ_MODEL, config.PROMPT_VERSION)
    if cached is not None:
        return cached
    result = llm.complete_text(CHAPTER_SYSTEM, combined, model=config.QUIZ_MODEL)
    cache.put("quiz_chapter_summary", result, combined, config.QUIZ_MODEL, config.PROMPT_VERSION)
    return result
