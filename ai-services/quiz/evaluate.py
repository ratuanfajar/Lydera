import config
import jsonutil
import llm

MAX_TOKENS = 2048

SYSTEM = (
    "Anda menilai catatan pengerjaan (langkah demi langkah) seorang siswa tunanetra SMA untuk satu "
    "soal matematika pilihan ganda yang dijawab SALAH. Bandingkan langkah siswa dengan langkah "
    "penyelesaian yang benar, cari PERSIS di langkah keberapa penalaran siswa pertama kali "
    "menyimpang, dan jelaskan kesalahannya dengan ramah -- tulisan Anda akan dibacakan pembaca "
    "layar, jadi hindari referensi visual (\"lihat di atas\", dst) dan tulis notasi matematika "
    "sebagai kata-kata, bukan simbol.\n\n"
    "Keluarkan HANYA JSON, tanpa markdown, dengan format:\n"
    '{"divergence_step": 2, "diagnosis": "...", "personalized_justification": "..."}\n'
    "divergence_step adalah nomor urut langkah SISWA (1-based) tempat penyimpangan pertama kali "
    "terjadi, atau null kalau siswa salah paham konsep sejak awal / langkahnya tidak bisa "
    "dicocokkan sama sekali dengan jalur penyelesaian yang benar."
)


def build_prompt(segment, question_text: str, options: dict, correct_option: str,
                  correct_langkah: list[str], kesimpulan: str,
                  student_option: str, student_langkah: list[str]) -> str:
    opsi_text = "\n".join(f"{label}. {text}" for label, text in options.items())
    correct_text = "\n".join(f"{i+1}. {t}" for i, t in enumerate(correct_langkah))
    student_text = "\n".join(f"{i+1}. {t}" for i, t in enumerate(student_langkah))
    return "\n\n".join([
        f"Materi sumber:\n{segment.text}",
        f"Soal:\n{question_text}\n\n{opsi_text}",
        f"Jawaban benar: {correct_option}. Langkah penyelesaian yang benar:\n{correct_text}\n"
        f"Kesimpulan: {kesimpulan}",
        f"Jawaban siswa: {student_option}. Langkah pengerjaan siswa:\n{student_text}",
    ])


def evaluate_scratchwork(segment, question_text: str, options: dict, correct_option: str,
                          correct_langkah: list[str], kesimpulan: str,
                          student_option: str, student_langkah: list[str]) -> dict:
    """Chain 5: bandingkan langkah pengerjaan siswa terhadap langkah penyelesaian yang benar,
    untuk soal yang dijawab salah. Tidak dicache -- hasilnya personal per siswa per attempt.
    Pemanggil (nanti: backend) yang memastikan ini cuma dipanggil saat student_option != correct_option."""
    prompt = build_prompt(segment, question_text, options, correct_option, correct_langkah,
                           kesimpulan, student_option, student_langkah)
    raw = llm.complete_text(SYSTEM, prompt, model=config.QUIZ_MODEL, max_tokens=MAX_TOKENS)
    return jsonutil.parse_json(raw)
