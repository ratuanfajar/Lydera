# Backend

FastAPI, arsitektur domain-driven (`app/domains/<domain>/{models,repositories,services,schemas,router.py}`), SQLAlchemy async + PostgreSQL, Alembic untuk migrasi skema, Redis + taskiq untuk pemrosesan async (ekstraksi MinerU, generate quiz).

## Struktur

- `app/main.py` — merakit seluruh router (prefix `/api`), middleware, dan exception handler.
- `app/core/` — koneksi DB (`db.py`, async SQLAlchemy), konfigurasi (`config.py`), keamanan/JWT (`security.py`), response envelope (`response.py`, `route.py`), broker taskiq (`taskiq.py`).
- `app/domains/contents/` — module, chapter, block, fase, cp. `services.py` juga menangani ingest hasil anotasi (`ingest_annotated_json`).
- `app/domains/quizz/` — quiz_request, quiz_request_chapter, soal, soal_opsi, soal_langkah, soal_stimulus. Lihat bagian "Hubungan dengan AI Service" di bawah.
- `app/domains/jobs/` — antrean job ekstraksi MinerU per bab.
- `app/tasks/` — task async lewat taskiq: `mineru_tasks.py` (ekstraksi + anotasi), `quiz_tasks.py` (generate quiz).
- `app/utils/` — `paths.py` (bridging `sys.path` ke `ai-services/annotation/` dan `ai-services/quiz/` untuk impor datar), `pdf_cut.py`, dan utilitas lain.

Detail parameter, response, dan kode error tiap endpoint ada di `CONTRACT.md` bagian 3 (perlu pembaruan menyusul restrukturisasi ini).

## Menjalankan

Butuh PostgreSQL, Redis, dan migrasi Alembic sudah dijalankan. Tiga proses:

```
# proses 1: API
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# proses 2: worker taskiq (memproses app/tasks/*)
taskiq worker app.core.taskiq:broker app.tasks.mineru_tasks app.tasks.quiz_tasks

# proses 3 (opsional, kalau dipakai): scheduler/consumer Redis pub/sub untuk progress streaming
```

Kalau `uv run uvicorn ...` gagal dengan error `Failed to canonicalize script path`, jalankan lewat modul Python langsung: `uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`.

## Hubungan dengan AI Service

Layanan AI anotasi (`ai-services/annotation/`) dan quiz generator (`ai-services/quiz/`) murni komputasi — tidak ada satu pun modulnya yang menyentuh DB. Backend yang membaca/menulis lewat repository masing-masing domain:

- **Anotasi**: `app/tasks/mineru_tasks.py` menjalankan `run_mineru.run_async` (progress streaming) lalu `pipeline.run` (annotate), kemudian memanggil `ContentService.ingest_annotated_json` untuk menyimpan block ke DB.
- **Quiz generator**: `app/tasks/quiz_tasks.py` membaca block bab dari DB, memanggil `quiz_pipeline.compute_for_chapter` (segmentasi, ringkas, generate, validate — lihat `ai-services/README.md`), lalu menyimpan tiap soal lewat `QuizRepository.save_soal`. Regenerasi cluster HOTS (`QuizService.regenerate_cluster`) memanggil `regenerate.compute_cluster` secara sinkron di request handler (bukan lewat task, karena hanya satu cluster, bukan satu bab penuh).

Kedua AI-service ini dijalankan lewat `asyncio.to_thread` dari task/service (fungsinya sinkron, memanggil LLM/MinerU) — bukan diimpor sebagai library async.

## Catatan

Impor antar `backend/`, `ai-services/annotation/`, dan `ai-services/quiz/` memakai gaya datar (`import config`, `import segment`, dst — lihat `app/utils/paths.py`, `ai-services/*/paths.py`). File spesifik satu fitur di `ai-services/` diberi prefiks nama fiturnya (`annotation_pipeline.py`, `quiz_pipeline.py`) untuk menghindari ambiguitas antara dua folder yang berbagi `sys.path` yang sama.

Migrasi Alembic untuk domain `quizz` (dan domain lain) belum pernah digenerate/dijalankan di repo ini (belum ada file di `alembic/versions/`) — perlu `alembic revision --autogenerate` + `alembic upgrade head` sebelum fitur quiz generator benar-benar bisa dites end-to-end ke database sungguhan.
