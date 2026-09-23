from annotation import config
from annotation import llm

LOTS_MAX_TOKENS = 1536
HOTS_MAX_TOKENS = 10240

SYSTEM = """# Peran
Anda membuat satu soal pilihan ganda matematika SMA untuk siswa tunanetra.

# Aturan Grounding
- Digroundkan penuh ke materi yang diberikan -- jangan mengarang fakta yang tidak ada di materi.
- Jangan menyalin ulang soal latihan yang sudah ada di materi.

# Kualitas Stem
- Satu fokus masalah saja, tanpa informasi yang tidak relevan.
- Hindari kalimat negatif ("manakah yang BUKAN...", "...kecuali") dan negasi ganda.
- Hanya ada SATU jawaban benar/paling tepat di antara opsi.

# Kualitas Distraktor
- Tiap opsi salah harus PLAUSIBEL -- berdasarkan miskonsepsi umum siswa, bukan opsi yang jelas
  mustahil atau konyol.
- Semua opsi (benar maupun salah) kira-kira SAMA panjang dan tingkat detailnya -- jawaban benar
  tidak boleh mencolok karena lebih panjang/rinci dari opsi lain.
- JANGAN pakai opsi "semua benar"/"tidak ada yang benar".
- Semua opsi konsisten tata bahasanya dengan stem dan satu sama lain.

# Gaya Penulisan
Bahasa Indonesia baku, jelas, ringkas, sesuai jenjang SMA -- tidak bertele-tele, tidak memakai
istilah di luar yang sudah dikenalkan di materi.

# Aksesibilitas
- Opsi jawaban harus jelas dibedakan kalau dibacakan pembaca layar -- hindari perbedaan yang cuma
  terlihat secara visual (notasi/simbol).
- Langkah penyelesaian berurutan dan lengkap, tidak perlu melihat ulang materi lain.

# Proses Berpikir
Isi "analisis_level" LEBIH DULU: 1-2 kalimat kenapa rancangan soal Anda benar-benar menuntut level
Bloom yang diminta, bukan level lain. Tulis soal final SETELAH itu, konsisten dengan analisis itu.

# Output
Keluarkan HANYA JSON, tanpa markdown, dengan format:
{"analisis_level": "...", "question_text": "...", "options": {"A": "...", "B": "...", "C": "...",
"D": "..."}, "correct_option": "A", "langkah": ["langkah 1", "langkah 2"], "kesimpulan": "...",
"stimulus": null}"""


BLOOM_GUIDANCE = {
    1: "C1 mengingat: soal menanyakan definisi/istilah/fakta LANGSUNG dari materi. JANGAN bungkus "
       "dengan skenario atau kasus baru yang perlu diproses -- begitu ada kasus/angka baru yang harus "
       "diolah, itu sudah bukan C1 lagi.",
    2: "C2 memahami: soal menanyakan penjelasan/parafrase konsep dengan kata-kata lain, atau minta "
       "mengenali contoh benar/salah dari sebuah konsep. JANGAN minta menghitung/menerapkan prosedur "
       "ke kasus baru -- itu levelnya di atas C2.",
    3: "C3 menerapkan: beri kasus/angka BARU (tidak ada di materi), siswa menerapkan SATU prosedur/rumus "
       "inti dari materi secara langsung untuk menyelesaikannya.",
    4: "C4 menganalisis: siswa membedah suatu situasi jadi beberapa bagian/hubungan sebab-akibat -- "
       "mis. menemukan asumsi yang keliru, membandingkan dua pendekatan dan menunjukkan bedanya, atau "
       "menelusuri di langkah mana sebuah penyelesaian jadi salah.",
    5: "C5 mengevaluasi: sajikan BEBERAPA pendekatan/klaim/solusi berbeda untuk kasus yang sama. Siswa "
       "menilai mana yang PALING VALID/EFISIEN berdasarkan kriteria tertentu. Opsi jawaban WAJIB berupa "
       "pendekatan/klaim berbeda (mis. 'Cara A benar karena...', 'Cara B salah karena...'), BUKAN sekadar "
       "angka hasil akhir yang berbeda -- kalau opsinya cuma angka berbeda, itu turun jadi C3.",
}


def build_prompt(segment, chapter_summary: str, bloom_level: int, feedback: str = "") -> str:
    parts = [
        f"# Konteks Bab\n{chapter_summary}",
        f"# Materi Sumber\n## {segment.title}\n{segment.text}",
        f"# Level yang Diminta\nC{bloom_level} -- {BLOOM_GUIDANCE[bloom_level]}",
    ]
    if bloom_level >= 4:
        parts.append(
            "# Stimulus\nIsi field \"stimulus\" dengan objek {\"readable_text\": \"...\"} berisi "
            "cerita/data/konteks aplikasi dunia nyata yang digroundkan ke materi sumber, dan soalnya "
            "harus butuh stimulus itu untuk dijawab."
        )
    if feedback:
        parts.append(f"# Koreksi Guru\n{feedback}\nPerbaiki sesuai koreksi ini.")
    return "\n\n".join(parts)


def generate_soal(segment, chapter_summary: str, bloom_level: int, feedback: str = "") -> dict:
    """Chain 3: hasilkan satu soal dari satu segmen + ringkasan bab."""
    prompt = build_prompt(segment, chapter_summary, bloom_level, feedback)
    max_tokens = HOTS_MAX_TOKENS if bloom_level >= 4 else LOTS_MAX_TOKENS
    effort = "medium" if bloom_level >= 4 else None
    data = llm.complete_json(
        SYSTEM, prompt, model=config.QUIZ_MODEL, max_tokens=max_tokens, effort=effort,
        required_keys=["analisis_level", "question_text", "options", "correct_option", "langkah",
                        "kesimpulan", "stimulus"],
    )
    data["bloom_level"] = bloom_level
    data["reading_order_start"] = segment.reading_order_start
    data["reading_order_end"] = segment.reading_order_end
    return data
