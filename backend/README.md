# Backend

FastAPI, arsitektur domain-driven (`app/domains/<domain>/{models,repositories,services,schemas,router.py,depedencies.py}`), SQLAlchemy async + PostgreSQL (pgvector), Alembic untuk migrasi skema, Redis + taskiq untuk pemrosesan async (ekstraksi MinerU, generate quiz, reindex chatbot, perhitungan progres, email).

## Struktur

- `app/main.py` — merakit seluruh router (prefix `/api`), middleware CORS, exception handler, endpoint `/health`, dan mount `/static/annotations` (isi `OUTPUT_DIR`, gambar hasil ekstraksi).
- `app/core/` — konfigurasi (`config.py`), koneksi DB (`db.py`), keamanan/JWT (`security.py`, dependency `Roles(...)`), response envelope (`response.py`, `route.py` → `WrappedRoute`), exception (`exceptions.py`), broker taskiq (`taskiq.py`), Redis (`redis.py`), email (`mail.py`), dan `model_registry.py` (impor semua model).
- `app/domains/` — satu folder per domain:
  - `users` (user, guru, siswa), `schools`, `cities`, `classrooms`, `otp` (reset password), `base`
  - `contents` — module, chapter, block, fase, cp, progres. `services.py` juga menangani ingest hasil anotasi (`ingest_annotated_json`) dan regenerasi blok.
  - `quizzer` — quiz_request, quiz_request_chapter, soal, soal_opsi, soal_langkah, soal_stimulus (`jenis` dan `spesifikasi` untuk stimulus bertipe), soal_jawaban, quiz_progress.
  - `evaluaizer` — letak kesalahan pada langkah siswa untuk jawaban salah (kolom pada `soal_jawaban`), hasil kuis siswa.
  - `jobs` — antrean job ekstraksi MinerU per bab.
  - `clarifier` — chat_session, chat_message, chapter_kb, block_embedding (pgvector), `sync_search.py`.
- `app/tasks/` — task async lewat taskiq:
  - `mineru_tasks.py` — ekstraksi MinerU + anotasi, lalu ingest ke DB
  - `quiz_tasks.py` — generate quiz
  - `process_exam_review_tasks.py` — hitung skor siswa setelah ujian
  - `chatbot_tasks.py` — reindex embedding bab/kelas
  - `evaluaizer_tasks.py` — analisis letak kesalahan jawaban salah siswa
  - `progress_tasks.py` — hitung ulang progres modul/bab
  - `email_tasks.py`, `file_tasks.py` — kirim email, bersihkan file PDF/output
- `app/utils/` — `paths.py` (menaruh `ai-services/` dan `backend/` ke `sys.path` untuk impor datar), `pdf_cut.py`, `idempotency.py`, `token.py`, `role.py`, `payload.py`.
- `migrations/` — Alembic: `versions/` (skema) dan `seeds/` (data referensi: kota, sekolah, kelas, fase/CP, akun contoh).

Kontrak API ada di koleksi Postman "Lydera" (sumber kebenaran) dan dapat dilihat di dokumentasi interaktif FastAPI pada `/docs` saat server berjalan. Format respons: `{"message": ..., "data": ...}`; error: `{"detail": ..., "errors": ...}`.

## Menjalankan

Butuh PostgreSQL (dengan ekstensi pgvector), Redis, `backend/.env` (contoh: `.env.example`), dan migrasi sudah dijalankan:

```
cd backend
uv run alembic upgrade head
```

Dua proses:

```
# API
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# worker taskiq (semua modul task)
uv run taskiq worker app.core.taskiq:broker app.tasks.mineru_tasks app.tasks.quiz_tasks app.tasks.process_exam_review_tasks app.tasks.chatbot_tasks app.tasks.progress_tasks app.tasks.email_tasks app.tasks.file_tasks app.tasks.evaluaizer_tasks
```

Kalau `uv run uvicorn ...` gagal dengan error `Failed to canonicalize script path`, jalankan lewat modul Python langsung: `uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`.

Di production, image Docker (`Dockerfile` di root) menjalankan uvicorn dari folder `backend/`; deploy lewat tag git (lihat `docs/runbooks/deploy-rollback.md`).

## Hubungan dengan AI Service

Layanan AI (`ai-services/annoter/`, `quizzer/`, `evaluaizer/`, `clarifier/`, dengan kode bersama di `common/`) murni komputasi — tidak ada satu pun modulnya yang menyentuh DB. Backend yang membaca/menulis lewat repository masing-masing domain:

- **Anotasi**: `app/tasks/mineru_tasks.py` menjalankan `run_mineru.run_async` (progress lewat Redis pub/sub) lalu `annoter_pipeline.run_with_report` (annotate tiap window; blok atau window yang gagal dilewati dan ditandai), kemudian memanggil `ContentService.ingest_annotated_json` untuk menyimpan block ke DB dan mengantre reindex chatbot. Regenerasi blok (`ContentService`) memanggil `annoter_regenerate`; guru juga bisa mengedit blok langsung lewat `PATCH /api/blocks/{block_id}` (spec 0008). Anotasi yang selesai mengantre reindex Clarifier otomatis; edit blok sesudahnya tidak, jadi reindex manual lewat endpoint Clarifier.
- **Quizzer**: `app/tasks/quiz_tasks.py` membaca block dan CP semua bab terpilih dari DB, memanggil `quizzer_pipeline.compute_for_quiz` sekali (segmentasi, ekstraksi poin, pemetaan, generate, verifikasi, laporan — lihat `ai-services/README.md` dan `docs/specs/0001-pipeline-quizzer-plan-then-generate.md`), lalu menyimpan soal (`source_point`) dan `coverage_report` lewat `QuizRepository.save_quiz_data`. Soal dengan rumus atau tabel menyimpan `markup` (JSONB di `soal`, `source_markup` di stimulus) di samping teks siap-baca. Satu slot gagal tidak membatalkan job. Regenerasi soal HOTS (`QuizService.regenerate_cluster`) memanggil `quizzer_regenerate.compute_regeneration` secara sinkron di request handler (bukan lewat task, karena scope-nya kecil), dan edit manual soal LOTS (`QuizService.edit_soal`) memverifikasi ulang soal lewat `review_soal` untuk memperbarui `review_priority` dan `validation_notes`.
- **Evaluaizer**: `evaluate_quiz_answers_task` (`app/tasks/evaluaizer_tasks.py`) menjalankan `AnswerEvaluator` (`domains/evaluaizer/evaluation.py`), yang memanggil `evaluaizer.evaluate.evaluate_scratchwork` untuk jawaban salah yang punya langkah dan menyimpan letak kesalahan; hasilnya ikut di hasil kuis siswa (spec 0009).
- **Clarifier**: `app/tasks/chatbot_tasks.py` meng-embed chunk (`clarifier.chunk.build_chunks`, ADR 0015) ke `block_embeddings`; `ChatbotService.ask` memanggil `clarifier.agent.run` dengan `search_module_executor` dari `sync_search.py` (pencarian pgvector). Siswa yang sedang mengerjakan kuis ditolak (400). Permintaan latihan soal dirangkai di service (`clarifier.practice` memilih sumber, `quizzer_pipeline.generate_practice` membuat dan memverifikasi soal) dan latihan hanya disimpan di Redis; semuanya lewat `POST /api/clarifier/sessions/{id}/messages`, tanpa endpoint terpisah (ADR 0014).

Fungsi AI sinkron (memanggil LLM/MinerU), jadi dijalankan lewat `asyncio.to_thread` dari task/service — bukan diimpor sebagai library async.

## Catatan

Impor antar `backend/` dan `ai-services/` berbasis paket (`from common import llm`, `from quizzer import quizzer_pipeline`); `ai-services/` ditaruh di `sys.path` oleh `app/utils/paths.py`.

Model baru wajib didaftarkan di `app/core/model_registry.py` dan diimpor di `migrations/env.py`. Migrasi awal `7687613b2cdc` (bernama "membuat table chatbot") sebenarnya membuat hampir seluruh skema dasar, termasuk tabel quiz; migrasi berikutnya menambah tabel OTP dan memperbaiki constraint.
