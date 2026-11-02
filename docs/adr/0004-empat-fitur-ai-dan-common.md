# 0004. Empat fitur AI bernama dan kode bersama di common/

- Status: diterima
- Tanggal: 2026-10

## Konteks

`ai-services` berisi tiga folder (`annotation/`, `quiz/`, `chatbot/`) yang saling mengimpor: semua fitur mengimpor `annotation.config/llm/cache`, dan `annotation/llm.py` mengimpor `quiz.jsonutil` (impor siklik). Analisis jawaban siswa tersembunyi di dalam `quiz/` sebagai "Chain 5". Prompt tersebar dalam paragraf di tiap modul tanpa format seragam.

## Keputusan

- Empat fitur bernama: **Annoter**, **Quizzer**, **Evaluaizer**, **Clarifier**. Folder `ai-services/` memakai nama itu (`annoter/`, `quizzer/`, `evaluaizer/`, `clarifier/`), begitu pula domain backend dan prefix API (`/annoter/...`, `/quizzer/...`, `/evaluaizer/...`, `/clarifier/...`). Nama tabel DB tidak berubah.
- Kode bersama pindah ke `ai-services/common/`: konfigurasi Azure dan default model, klien LLM, cache, `jsonutil`, paralelisme, `prompt_format`. Konfigurasi per fitur ada di `<fitur>/config.py`.
- Impor berbasis paket (`from common import llm`); `ai-services/` ada di `sys.path` (backend lewat `app/utils/paths.py`, Dockerfile lewat `PYTHONPATH`). CLI dijalankan sebagai `python -m <fitur>.<modul>` dari `ai-services/`.
- Evaluaizer menjadi domain backend sendiri. Tanpa alias rute lama karena frontend belum ada.

## Konsekuensi

- Siklus impor hilang; tiap fitur hanya bergantung pada `common/`.
- Rute lama memutus koleksi Postman lama; koleksi "Lydera" sudah disinkronkan.
- `jobs.out_dir` di DB menyimpan path absolut ke folder output; database yang sudah berisi job perlu `OUTPUT_DIR` atau `jobs.out_dir` disesuaikan (lihat runbook).
- Dokumen yang menyebut nama lama harus diperbarui bersamaan dengan fiturnya.
