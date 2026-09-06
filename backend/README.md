# Backend

Storage hasil anotasi ke database, ekspos lewat FastAPI, dan orkestrasi pemrosesan bab (potong PDF, panggil MinerU + anotasi, ingest ke DB). Database memakai PostgreSQL lewat `psycopg`, tanpa ORM.

## Files

### schema.sql
Definisi seluruh tabel database, dijalankan oleh `db.init_db()`. Detail skema ada di `CONTRACT.md`.

`schema.sql` dijalankan ulang setiap start, memakai `CREATE TABLE IF NOT EXISTS` dan `ADD COLUMN IF NOT EXISTS` supaya aman dipanggil berkali-kali. Batasannya: `ADD COLUMN IF NOT EXISTS` hanya memeriksa keberadaan kolom, bukan constraint-nya — kalau sebuah FK constraint pernah di-drop manual (mis. lewat `DROP TABLE ... CASCADE` pada tabel yang direferensikan) sementara kolomnya sendiri tetap ada, re-run `init_db()` tidak akan memulihkan constraint itu. Ini bukan pengganti sistem migrasi sungguhan (mis. Alembic) — cukup untuk tahap sekarang, tapi kalau skema makin sering berubah setelah pilot test, pertimbangkan pindah ke migration tool yang melacak versi skema secara eksplisit.

### db.py
Koneksi dan inisialisasi database lewat `psycopg`, dengan `row_factory=dict_row` (baris dikembalikan sebagai dict).

- `connect()` membuka koneksi ke `DATABASE_URL` (dari `backend/.env`, contoh nilai di `.env.example`).
- `init_db()` menjalankan `schema.sql`.

### ingest.py
Membuat modul dan bab, lalu menyimpan blok dari `annotated.json` ke sebuah bab.

- `create_module(conn, title, fase_id)` membuat baris modul dan mengembalikan `module_id`.
- `create_chapter(conn, module_id, number, title, source_file, cp_id)` membuat baris bab di bawah modul dan mengembalikan `chapter_id`.
- `ingest(conn, annotated_path, chapter_id)` membaca `annotated.json` dan menyisipkan blok ke bab tersebut. Mengembalikan jumlah blok.
- `current_max_order(conn, chapter_id)` mengembalikan `reading_order` terbesar milik bab.

Blok disimpan secara bertahap dalam satu bab. `reading_order` dihitung dari nilai terbesar yang ada ditambah kelipatan `READING_ORDER_STEP` (10), sehingga beberapa window dari satu bab yang diproses terpisah tetap menyambung.

### pdf_cut.py
Memotong PDF ke rentang halaman tertentu (0-based, inklusif) lewat `pypdf`. Dipakai `app/routers/chapters.py` untuk memotong PDF modul yang di-upload guru sesuai rentang halaman satu bab, sebelum diproses MinerU.

### jobs.py
Queue pemrosesan bab berbasis tabel `job`.

- `enqueue(conn, chapter_id, pdf_path, out_dir)` memasukkan satu job, mengembalikan `job_id`.
- `get_latest_job_for_chapter(conn, chapter_id)` mengambil job terakhir milik satu bab.
- `run_worker_forever()` menjalankan loop worker tanpa henti; dipakai oleh `worker.py`.

Worker memproses job satu per satu (tidak paralel) karena MinerU membutuhkan RAM besar per proses; menjalankan lebih dari satu worker MinerU sekaligus berisiko kehabisan memori.

### worker.py
Proses worker MinerU, terpisah dari proses Uvicorn, **selalu dijalankan sebagai proses tersendiri** (bukan bagian dari proses API) supaya jumlahnya tetap tepat satu tidak peduli berapa banyak proses Uvicorn yang melayani HTTP. Wajib tepat satu instance berjalan.

```
uv run python worker.py
```

### paths.py
`setup()` menaruh folder `backend/` dan `ai services/annotation/` ke `sys.path`, supaya impor datar (`import db`, `import config`, dst) bisa jalan dari kedua arah tanpa tiap entry point menghitung ulang lokasinya sendiri. Dipanggil `worker.py`, `jobs.py`, dan `app/main.py`.

### app/
Aplikasi FastAPI.

- `app/main.py` merakit semua router dan menjalankan `db.init_db()` saat start.
- `app/schemas.py` model request/response Pydantic.
- `app/routers/modules.py` — `POST /modules`, `GET /modules`, `GET /modules/{id}/cp`.
- `app/routers/chapters.py` — `POST /chapters` (upload PDF + rentang halaman, memotong PDF, membuat bab, mengantrekan job), `GET /chapters/{id}`, `GET /chapters/{id}/status`.
- `app/routers/blocks.py` — `GET /chapters/{id}/blocks`, `POST /blocks/{id}/regenerate`.
- `app/routers/fase.py` — `GET /fase`.

Detail parameter, response, dan kode error tiap endpoint ada di `CONTRACT.md` bagian 3 — bukan di sini.

Menjalankan (dua proses terpisah, wajib dua-duanya):

```
# proses 1: worker MinerU
uv run python worker.py

# proses 2: API
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

`app/main.py` sendiri tidak pernah menjalankan worker MinerU, jadi `--workers` di Uvicorn boleh dinaikkan bebas untuk melayani lebih banyak request HTTP tanpa memengaruhi jumlah proses MinerU yang berjalan (tetap satu, dari `worker.py`).

## Konfigurasi

`backend/.env` (salin dari `.env.example`):

| Variabel | Default | Keterangan |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:[PASSWORD]@localhost:5432/lydera` | Koneksi PostgreSQL |

`DATABASE_URL` adalah nama generik (dipakai banyak framework/platform lain, mis. Heroku). Kalau proses ini nanti berjalan berdampingan dengan aplikasi lain di environment yang sama, pastikan tidak bentrok dengan variabel `DATABASE_URL` milik aplikasi lain.

## Hubungan dengan AI Service

Layanan AI (`ai services/annotation/`) menghasilkan `annotated.json` per window bab. `jobs.py` menjalankan `batch.plan` + `run_mineru.run` per window, lalu `pipeline.run` untuk menganotasi dan meng-ingest seluruh window bab tersebut ke satu `chapter`.

## Catatan

Impor antar modul di `backend/` dan `ai services/annotation/` memakai gaya datar (`import db`, `import config`, dst — lihat `paths.py`). Ini aman selama layanan AI berdiri sendiri, tapi berisiko bentrok nama modul (`config`, `db`, `batch`, dst adalah nama umum) kalau `backend/app` disatukan langsung ke proses FastAPI aplikasi utama yang mungkin punya modul dengan nama sama. Sebelum penggabungan itu terjadi, sebaiknya: (a) folder `ai services/annotation` diganti nama jadi identifier Python valid (mis. `ai_services/annotation`, karena nama dengan spasi tidak bisa jadi package Python), (b) tambahkan `__init__.py` di `ai_services/`, `ai_services/annotation/`, dan `backend/`, (c) ganti seluruh `import X` datar di kedua folder itu jadi impor bernamespace (`from ai_services.annotation import X` atau `from backend import X`). Perubahan ini sengaja belum dikerjakan sekarang karena bentuk package yang tepat bergantung pada struktur BE utama yang belum diketahui detailnya.
