import config
import jsonutil
import llm

LOTS_MAX_TOKENS = 1536
HOTS_MAX_TOKENS = 3072

SYSTEM = (
    "Anda membuat satu soal pilihan ganda matematika SMA untuk siswa tunanetra, berdasarkan materi "
    "yang diberikan. Soal harus digroundkan penuh ke materi itu -- jangan mengarang fakta yang tidak "
    "ada di materi, dan jangan menyalin ulang soal latihan yang sudah ada di materi tersebut. Opsi "
    "jawaban harus jelas dibedakan kalau dibacakan pembaca layar (hindari perbedaan yang cuma "
    "terlihat secara visual, seperti notasi atau simbol). Langkah penyelesaian harus berurutan dan "
    "lengkap tanpa perlu melihat ulang materi lain.\n\n"
    "Keluarkan HANYA JSON, tanpa markdown, dengan format:\n"
    '{"question_text": "...", "options": {"A": "...", "B": "...", "C": "...", "D": "..."}, '
    '"correct_option": "A", "langkah": ["langkah 1", "langkah 2"], "kesimpulan": "...", '
    '"stimulus": null}'
)


def build_prompt(segment, chapter_summary: str, bloom_level: int, feedback: str = "") -> str:
    kind = "HOTS (analisis/evaluasi/kreasi)" if bloom_level >= 4 else "LOTS (mengingat/memahami/menerapkan)"
    parts = [
        f"Konteks bab secara keseluruhan: {chapter_summary}",
        f"Materi sumber (bagian '{segment.title}'):\n{segment.text}",
        f"Buat satu soal {kind} (level Bloom C{bloom_level}) dari materi di atas.",
    ]
    if bloom_level >= 4:
        parts.append(
            "Soal ini HOTS: isi field \"stimulus\" dengan objek {\"readable_text\": \"...\"} berisi "
            "cerita/data/konteks aplikasi dunia nyata yang digroundkan ke materi sumber, dan soalnya "
            "harus butuh stimulus itu untuk dijawab."
        )
    if feedback:
        parts.append(f"Koreksi dari guru terhadap soal versi sebelumnya: {feedback}\nPerbaiki sesuai koreksi ini.")
    return "\n\n".join(parts)


def generate_soal(segment, chapter_summary: str, bloom_level: int, feedback: str = "") -> dict:
    """Chain 3: hasilkan satu soal dari satu segmen + ringkasan bab. Tidak dicache -- tiap soal harus baru.

    `feedback` diisi kalau ini regenerasi atas koreksi guru (cluster HOTS), kosong untuk generate awal."""
    prompt = build_prompt(segment, chapter_summary, bloom_level, feedback)
    max_tokens = HOTS_MAX_TOKENS if bloom_level >= 4 else LOTS_MAX_TOKENS
    raw = llm.complete_text(SYSTEM, prompt, model=config.QUIZ_MODEL, max_tokens=max_tokens)
    data = jsonutil.parse_json(raw)
    data["bloom_level"] = bloom_level
    data["reading_order_start"] = segment.reading_order_start
    data["reading_order_end"] = segment.reading_order_end
    return data
