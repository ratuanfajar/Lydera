import cache
import config
import llm

SYSTEM = (
    "Anda membaca tabel dari buku matematika untuk siswa tunanetra. Berdasarkan gambar "
    "tabel dan HTML hasil OCR (yang mungkin memuat sel rusak atau kosong), ubah tabel "
    "menjadi teks linear Bahasa Indonesia yang dibacakan pembaca layar: sebutkan judul "
    "tiap kolom lalu tiap baris beserta nilainya. Perbaiki sel yang jelas salah OCR "
    "berdasarkan gambar. Tulis langsung sebagai kalimat mengalir tanpa kalimat pembuka; "
    "jangan mulai dengan 'Berikut' atau 'Berdasarkan', dan jangan menyebut 'tabel tersebut', "
    "'HTML', atau 'gambar yang diberikan'. Jangan gunakan markdown, tanda bintang, atau "
    "tanda pagar. Keluarkan hanya teks bacaannya."
)


def linearize_table(block) -> str:
    """Ubah tabel menjadi teks linear via MLLM (gambar + HTML OCR), memakai cache."""
    if not (block.image_path and block.image_path.exists()):
        return block.caption
    cached = cache.get("table", block.image_path.stem, config.VISION_MODEL, config.PROMPT_VERSION)
    if cached is None:
        cached = llm.complete_vision(SYSTEM, build_prompt(block.caption, block.table_html), block.image_path)
        cache.put("table", cached, block.image_path.stem, config.VISION_MODEL, config.PROMPT_VERSION)
    return cached


def build_prompt(caption: str, table_html: str) -> str:
    parts = []
    if caption:
        parts.append(f"Keterangan: {caption}")
    if table_html:
        parts.append(f"HTML hasil OCR:\n{table_html}")
    parts.append("Bacakan tabel ini.")
    return "\n".join(parts)
