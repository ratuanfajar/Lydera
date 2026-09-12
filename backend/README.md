# Backend

Storage hasil anotasi ke database, ekspos lewat FastAPI, dan orkestrasi pemrosesan bab (potong PDF, panggil MinerU + anotasi, ingest ke DB). Database memakai PostgreSQL lewat `psycopg`, tanpa ORM.

## Files

### schema.sql
Definisi seluruh tabel database, dijalankan oleh `db.init_db()`. Detail skema ada di `CONTRACT.md`.

Dijalankan ulang setiap start, memakai `CREATE TABLE IF NOT EXISTS` dan `ADD COLUMN IF NOT EXISTS`. `ADD COLUMN IF NOT EXISTS` hanya memeriksa keberadaan kolom, bukan constraint-nya — FK constraint yang di-drop manual tidak ikut dipulihkan. Bukan sistem migrasi (mis. Alembic).

### db.py
Koneksi dan inisialisasi database lewat `psycopg`, dengan `row_factory=dict_row` (baris dikembalikan sebagai dict).

- `connect()` membuka koneksi ke `DATABASE_URL` (dari `backend/.env`, contoh nilai di `.env.example`).
- `init_db()` menjalankan `schema.sql`.

### annotation_ingest.py
Membuat modul dan bab, lalu menyimpan blok dari `annotated.json` ke sebuah bab.

- `create_module(conn, title, fase_id)` membuat baris modul dan mengembalikan `module_id`.
- `create_chapter(conn, module_id, number, title, source_file, cp_id)` membuat baris bab di bawah modul dan mengembalikan `chapter_id`.
- `ingest(conn, annotated_path, chapter_id)` membaca `annotated.json` dan menyisipkan blok ke bab tersebut. Mengembalikan jumlah blok.
- `current_max_order(conn, chapter_id)` mengembalikan `reading_order` terbesar milik bab.

Blok disimpan secara bertahap dalam satu bab. `reading_order` dihitung dari nilai terbesar yang ada ditambah kelipatan `READING_ORDER_STEP` (10), sehingga beberapa window dari satu bab yang diproses terpisah tetap menyambung.

### quiz_ingest.py
Menyimpan hasil quiz generator ke DB.

- `create_quiz_request(conn, module_id)` membuat baris `quiz_request`, mengembalikan `quiz_request_id`.
- `link_chapter(conn, quiz_request_id, chapter_id, hots_count, lots_count)` mengaitkan satu bab ke request dengan target jumlah soalnya.
- `save_soal(conn, quiz_request_id, chapter_id, data, review_priority, validation_notes)` menyimpan satu soal (opsi, langkah, dan stimulus kalau HOTS). Satu commit per soal.

### pdf_cut.py
Memotong PDF ke rentang halaman tertentu (0-based, inklusif) lewat `pypdf`. Dipakai `app/routers/chapters.py` untuk memotong PDF modul sesuai rentang halaman satu bab, sebelum diproses MinerU.

### jobs.py
Queue pemrosesan bab berbasis tabel `job`.

- `enqueue(conn, chapter_id, pdf_path, out_dir)` memasukkan satu job, mengembalikan `job_id`.
- `get_latest_job_for_chapter(conn, chapter_id)` mengambil job terakhir milik satu bab.
- `run_worker_forever()` menjalankan loop worker tanpa henti; dipakai oleh `annotation_worker.py`.

Worker memproses job satu per satu karena MinerU membutuhkan RAM besar per proses dan model MinerU tetap resident di memori selama proses ini hidup. Wajib tepat satu instance.

### annotation_worker.py
Proses worker MinerU, terpisah dari proses Uvicorn, selalu dijalankan sebagai proses tersendiri. Wajib tepat satu instance berjalan.

```
uv run python annotation_worker.py
```

### quiz_worker.py
Proses worker quiz generator, terpisah dari proses Uvicorn dan dari `annotation_worker.py`. Polling tabel `quiz_request` (status `queued`), menjalankan Chain 0-4 (`ai services/quiz/quiz_pipeline.py`) per bab yang diminta lewat `quiz_request_chapter`. Bebannya cuma panggilan API (LLM), bukan proses lokal berat seperti MinerU — boleh dijalankan lebih dari satu instance.

```
uv run python quiz_worker.py
```

`annotation_worker.py` dan `quiz_worker.py` dipisah karena karakteristiknya berbeda: satu wajib singleton dan menahan model resident di memori, satu lagi ringan dan boleh diskalakan. Memisahkan keduanya memberi isolasi kegagalan dan skala independen untuk masing-masing.

### paths.py
`setup()` menaruh folder `backend/`, `ai services/annotation/`, dan `ai services/quiz/` ke `sys.path`, supaya impor datar (`import db`, `import config`, dst) bisa jalan dari ketiga arah. Dipanggil `annotation_worker.py`, `quiz_worker.py`, `jobs.py`, dan `app/main.py`.

### app/
Aplikasi FastAPI.

- `app/main.py` merakit semua router dan menjalankan `db.init_db()` saat start.
- `app/schemas.py` model request/response Pydantic.
- `app/routers/modules.py` — `POST /modules`, `GET /modules`, `GET /modules/{id}/cp`.
- `app/routers/chapters.py` — `POST /chapters` (upload PDF + rentang halaman, memotong PDF, membuat bab, mengantrekan job), `GET /chapters/{id}`, `GET /chapters/{id}/status`.
- `app/routers/blocks.py` — `GET /chapters/{id}/blocks`, `POST /blocks/{id}/regenerate`.
- `app/routers/fase.py` — `GET /fase`.
- `app/routers/quiz.py` — `POST /quiz-requests`, `GET /quiz-requests/{id}/status`, `GET /quiz-requests/{id}/soal`.
- `app/routers/soal.py` — `GET /soal/{id}`, `PATCH /soal/{id}`, `POST /soal/{id}/approve`, `POST /soal/{id}/reject`, `POST /soal/{id}/regenerate`.

Detail parameter, response, dan kode error tiap endpoint ada di `CONTRACT.md` bagian 3.

Menjalankan (tiga proses terpisah, wajib semuanya):

```
# proses 1: worker MinerU
uv run python annotation_worker.py

# proses 2: worker quiz generator
uv run python quiz_worker.py

# proses 3: API
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

Kalau `uv run uvicorn ...` gagal dengan error `Failed to canonicalize script path`, jalankan lewat modul Python langsung: `uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2`.

`app/main.py` tidak pernah menjalankan worker MinerU atau quiz generator, jadi `--workers` di Uvicorn boleh dinaikkan bebas tanpa memengaruhi jumlah proses worker.

## Konfigurasi

`backend/.env` (salin dari `.env.example`):

| Variabel | Default | Keterangan |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:[PASSWORD]@localhost:5432/lydera` | Koneksi PostgreSQL |

`DATABASE_URL` adalah nama generik — cek tidak bentrok kalau proses ini berjalan berdampingan dengan aplikasi lain di environment yang sama.

## Hubungan dengan AI Service

Layanan AI anotasi (`ai services/annotation/`) menghasilkan `annotated.json` per window bab. `jobs.py` menjalankan `batch.plan` + `run_mineru.run` per window, lalu `annotation_pipeline.run` untuk menganotasi dan meng-ingest seluruh window bab ke satu `chapter`.

Layanan AI quiz generator (`ai services/quiz/`) berbeda pola dari anotasi: modul-modulnya (`segment.py`, `context.py`, `generate.py`, `validate.py`, `regenerate.py`) tidak menyentuh DB, tapi `quiz_pipeline.py` memanggil `backend/quiz_ingest.py` langsung untuk menyimpan hasil — mirip `annotation_pipeline.py` (orkestrator yang boleh menyentuh DB), bukan modul konversi individualnya.

## Catatan

Impor antar modul di `backend/`, `ai services/annotation/`, dan `ai services/quiz/` memakai gaya datar (`import db`, `import config`, dst — lihat `paths.py`). File spesifik satu fitur diberi prefiks nama fiturnya (`annotation_*`/`quiz_*`) untuk menghindari ambiguitas dan bentrok impor antar fitur yang berbagi `sys.path` yang sama: `annotation_worker.py`, `annotation_ingest.py`, `annotation_pipeline.py`, `quiz_worker.py`, `quiz_ingest.py`, `quiz_pipeline.py`. File generik/dipakai bersama (`db.py`, `cache.py`, `llm.py`, `config.py`, `paths.py`) tidak diberi prefiks.

Sebelum folder-folder ini disatukan ke proses FastAPI aplikasi utama, impor datar perlu diganti jadi impor bernamespace (butuh restrukturisasi folder jadi package Python yang valid).
