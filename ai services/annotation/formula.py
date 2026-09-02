import cache
import config
import llm

SYSTEM = (
    "Anda mengubah notasi matematika LaTeX menjadi cara membacanya dalam Bahasa "
    "Indonesia yang natural untuk dibacakan pembaca layar kepada siswa tunanetra. "
    "Baca bilangan sesuai nilai tempatnya, contoh 250 dibaca 'dua ratus lima puluh'. "
    "Jangan akhiri hasil dengan tanda baca. "
    "Keluarkan hanya hasil bacaannya tanpa penjelasan tambahan."
)


def convert_formula(latex: str) -> str:
    """Ubah satu rumus LaTeX menjadi lafal Bahasa Indonesia, memakai cache."""
    latex = latex.strip()
    if not latex:
        return ""
    cached = cache.get("formula", latex, config.TEXT_MODEL, config.PROMPT_VERSION)
    if cached is None:
        cached = llm.complete_text(SYSTEM, latex)
        cache.put("formula", cached, latex, config.TEXT_MODEL, config.PROMPT_VERSION)
    return cached
