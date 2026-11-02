# Dev lokal

Prasyarat: Python 3.12, uv, PostgreSQL dengan ekstensi pgvector, Redis. MinerU memakai torch versi CPU (index `pytorch-cpu` di `pyproject.toml`); GPU opsional dengan mengganti index ke cu126.

## Setup

```
uv sync
```

Salin `backend/.env.example` menjadi `backend/.env` dan `ai-services/.env.example` menjadi `ai-services/.env`, lalu isi nilainya (DB, `REDIS_URL`, kunci JWT/secret, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`). Jangan commit berkas `.env`.

## Database

```
cd backend
uv run alembic upgrade head
```

Seed data referensi ada di `backend/migrations/seeds/`.

## Menjalankan

Dua proses terpisah (API dan worker), keduanya dari `backend/`:

```
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
uv run taskiq worker app.core.taskiq:broker app.tasks.mineru_tasks app.tasks.quiz_tasks app.tasks.process_exam_review_tasks app.tasks.chatbot_tasks app.tasks.progress_tasks app.tasks.email_tasks app.tasks.file_tasks app.tasks.evaluaizer_tasks
```

Redis dan PostgreSQL harus sudah jalan. Cek: `GET /health` dan dokumentasi interaktif di `/docs`.

Jika uvicorn gagal dengan `Failed to canonicalize script path`, jalankan `uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`.

## Debug satu tahap AI

Modul di `ai-services/annoter/` dan `ai-services/quizzer/` punya CLI; jalankan dari `ai-services/` dengan `uv run python -m <fitur>.<modul> ...` (mis. `python -m annoter.batch --pdf ...`). Output MinerU di `ai-services/annoter/output`, cache MLLM di `ai-services/.cache` (hapus cache bila perlu hasil segar).

Tabel `jobs` menyimpan `out_dir` sebagai path absolut. Setelah folder `annotation/` berganti nama menjadi `annoter/`, database yang sudah berisi job harus memperbarui `jobs.out_dir` (atau mengarahkan setting `OUTPUT_DIR` backend ke lokasi lama); tanpa itu pencarian gambar saat regenerasi gagal.

Di mesin ber-VRAM kecil (sekitar 4 GB), proses sedikit halaman per run: `python -m annoter.batch --max-pages 3` untuk formula + tabel.
