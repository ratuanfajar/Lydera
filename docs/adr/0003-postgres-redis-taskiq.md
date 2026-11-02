# 0003. PostgreSQL, Redis, dan taskiq untuk backend

- Status: diterima
- Tanggal: 2026-09

## Konteks

Prototipe awal memakai SQLite. Produk kini butuh banyak pengguna (guru, siswa), relasi kompleks (modul, bab, blok, soal, progres), pencarian vektor untuk chatbot, dan pekerjaan lama (MinerU per window halaman, generate quiz, embedding) yang tidak boleh memblokir request.

## Keputusan

- PostgreSQL dengan pgvector, diakses lewat SQLAlchemy async (asyncpg). Skema dikelola Alembic.
- Redis sebagai broker taskiq (`ListQueueBroker`), result backend, cache chatbot, dan progress streaming.
- Pekerjaan berat berjalan di worker taskiq; fungsi ai-services yang sinkron dipanggil dengan `asyncio.to_thread`.
- Arsitektur backend domain-driven: `app/domains/<domain>/{models,repositories,schemas,services,router,depedencies}`.

## Konsekuensi

- Butuh tiga proses saat dev: API, worker taskiq, dan Redis + PostgreSQL berjalan.
- Skema berubah hanya lewat migrasi Alembic; model baru terdaftar di `model_registry.py` dan `migrations/env.py`.
- Dimensi embedding (3072) terikat pada tipe kolom; mengganti model embedding berarti migrasi dan embed ulang.
