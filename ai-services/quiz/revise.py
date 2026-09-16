import config
import jsonutil
import llm

REVISE_SOAL_MAX_TOKENS = 3072
REVISE_STIMULUS_MAX_TOKENS = 1536
RECHECK_SOAL_MAX_TOKENS = 3072

REVISE_SOAL_SYSTEM = (
    "Anda mengedit SATU soal pilihan ganda matematika yang SUDAH ADA, berdasarkan feedback guru. "
    "Soal ini bagian dari kelompok yang berbagi satu stimulus/konteks cerita -- JANGAN mengubah "
    "skenario stimulus, dan JANGAN mengarang ulang soal dari nol. Ubah HANYA bagian yang diminta "
    "feedback, pertahankan sisanya persis seperti semula.\n\n"
    "Kalau feedback ini sebenarnya menuntut perubahan pada STIMULUS itu sendiri (bukan cuma soal "
    "ini) -- misalnya stimulusnya kepanjangan atau datanya salah -- set \"needs_stimulus_change\": "
    "true dan isi \"stimulus_change_reason\", TANPA mengubah field soal lainnya.\n\n"
    "Keluarkan HANYA JSON, tanpa markdown, dengan format:\n"
    '{"needs_stimulus_change": false, "stimulus_change_reason": null, "question_text": "...", '
    '"options": {"A": "...", "B": "...", "C": "...", "D": "..."}, "correct_option": "A", '
    '"langkah": ["langkah 1", "langkah 2"], "kesimpulan": "..."}'
)

REVISE_STIMULUS_SYSTEM = (
    "Anda mengedit satu stimulus (cerita/konteks aplikasi dunia nyata) yang SUDAH ADA untuk "
    "kelompok soal matematika, berdasarkan feedback guru. JANGAN mengarang stimulus baru dari nol "
    "-- edit yang ada seminimal mungkin sesuai feedback, tetap digroundkan ke materi sumber.\n\n"
    "Keluarkan HANYA JSON, tanpa markdown, dengan format:\n"
    '{"readable_text": "..."}'
)

RECHECK_SOAL_SYSTEM = (
    "Stimulus bersama untuk sekelompok soal matematika baru saja direvisi. Periksa satu soal "
    "berikut: apakah masih konsisten dan bisa dijawab dari stimulus yang baru? Kalau ya, "
    "kembalikan isinya PERSIS seperti semula (jangan diubah tanpa alasan). Kalau tidak (butuh "
    "detail dari stimulus lama yang sudah berubah/hilang), sesuaikan seperlunya SAJA -- jangan "
    "mengarang ulang dari nol.\n\n"
    "Keluarkan HANYA JSON, tanpa markdown, dengan format:\n"
    '{"question_text": "...", "options": {"A": "...", "B": "...", "C": "...", "D": "..."}, '
    '"correct_option": "A", "langkah": ["langkah 1", "langkah 2"], "kesimpulan": "..."}'
)


def _format_soal(soal: dict) -> str:
    opsi_text = "\n".join(f"{label}. {text}" for label, text in soal["options"].items())
    langkah_text = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(soal["langkah"]))
    return (
        f"{soal['question_text']}\n\n{opsi_text}\n\n"
        f"Jawaban benar: {soal['correct_option']}\nLangkah:\n{langkah_text}\nKesimpulan: {soal['kesimpulan']}"
    )


def build_revise_soal_prompt(segment, stimulus_text: str, soal: dict, feedback: str) -> str:
    parts = [f"Materi sumber:\n{segment.text}"]
    if stimulus_text:
        parts.append(f"Stimulus (dipakai bersama beberapa soal lain, JANGAN diubah kecuali memang diperlukan):\n{stimulus_text}")
    parts.append(f"Soal saat ini:\n{_format_soal(soal)}")
    parts.append(f"Feedback guru: {feedback}")
    return "\n\n".join(parts)


def revise_soal(segment, stimulus_text: str, soal: dict, feedback: str) -> dict:
    """Chain 3.5a: edit satu soal yang dikritik guru, dengan konteks soal+stimulus lama sebagai
    anchor -- bukan generate dari nol. Melaporkan balik lewat `needs_stimulus_change` kalau
    perbaikannya sebenarnya perlu sampai ke stimulus (shared ke soal lain)."""
    prompt = build_revise_soal_prompt(segment, stimulus_text, soal, feedback)
    raw = llm.complete_text(REVISE_SOAL_SYSTEM, prompt, model=config.QUIZ_MODEL, max_tokens=REVISE_SOAL_MAX_TOKENS)
    return jsonutil.parse_json(raw)


def revise_stimulus(segment, stimulus_text: str, feedback: str) -> str:
    """Chain 3.5b: edit stimulus yang sudah ada seminimal mungkin sesuai feedback -- bukan
    mengarang stimulus baru. Dipanggil hanya kalau `revise_soal` menandai needs_stimulus_change."""
    prompt = (
        f"Materi sumber:\n{segment.text}\n\n"
        f"Stimulus saat ini:\n{stimulus_text}\n\n"
        f"Feedback guru: {feedback}"
    )
    raw = llm.complete_text(REVISE_STIMULUS_SYSTEM, prompt, model=config.QUIZ_MODEL, max_tokens=REVISE_STIMULUS_MAX_TOKENS)
    return jsonutil.parse_json(raw)["readable_text"]


def recheck_soal_for_new_stimulus(segment, new_stimulus_text: str, soal: dict) -> dict:
    """Chain 3.5c: setelah stimulus berubah, periksa satu soal (bisa yang dikritik ATAU soal lain
    di cluster yang sama) masih konsisten -- kembalikan apa adanya kalau ya, sesuaikan seperlunya
    kalau tidak. Dipanggil untuk SEMUA soal di cluster, bukan cuma yang dikritik guru."""
    prompt = (
        f"Materi sumber:\n{segment.text}\n\n"
        f"Stimulus baru:\n{new_stimulus_text}\n\n"
        f"Soal saat ini:\n{_format_soal(soal)}"
    )
    raw = llm.complete_text(RECHECK_SOAL_SYSTEM, prompt, model=config.QUIZ_MODEL, max_tokens=RECHECK_SOAL_MAX_TOKENS)
    return jsonutil.parse_json(raw)
