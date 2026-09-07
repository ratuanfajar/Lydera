import cache
import config
import llm

SYSTEM = (
    "Anda mendeskripsikan gambar dari buku matematika SMA untuk siswa tunanetra. "
    "Jelaskan makna gambar secara ringkas dan informatif dalam Bahasa Indonesia: untuk "
    "grafik sebutkan sumbu, satuan, tren, dan nilai penting secara ringkas tanpa "
    "menyebutkan setiap titik data satu per satu; untuk diagram sebutkan hubungan yang "
    "ditunjukkan. Tulis langsung tanpa kalimat pembuka; jangan mulai dengan 'Gambar "
    "menunjukkan', 'Berikut', atau 'Berdasarkan gambar', dan jangan menyebut proses OCR "
    "atau HTML. Jangan gunakan markdown, tanda bintang, atau tanda pagar. Keluarkan hanya "
    "deskripsinya."
)


def caption_image(block, context: str = "") -> str:
    """Hasilkan caption Bahasa Indonesia untuk gambar/chart, memakai cache."""
    if not (block.image_path and block.image_path.exists()):
        return ""
    cached = cache.get("image", block.image_path.stem, config.VISION_MODEL, config.PROMPT_VERSION)
    if cached is None:
        cached = llm.complete_vision(SYSTEM, build_prompt(block.caption, context), block.image_path)
        cache.put("image", cached, block.image_path.stem, config.VISION_MODEL, config.PROMPT_VERSION)
    return cached


def build_prompt(caption: str, context: str) -> str:
    parts = []
    if caption:
        parts.append(f"Keterangan asli: {caption}")
    if context:
        parts.append(f"Konteks di sekitarnya: {context}")
    parts.append("Deskripsikan gambar ini.")
    return "\n".join(parts)
