# Backend

FastAPI async, SQLAlchemy 2 (async), PostgreSQL + pgvector, Alembic, Redis, taskiq. Semua router di bawah prefix `/api` (dirakit di `app/main.py`).

## Struktur domain

`app/domains/<domain>/`:

```
models/            SQLAlchemy, Mapped[...] / mapped_column
repositories/      interface.py (ABC) + repository.py (implementasi)
schemas/           Pydantic request/response
services.py        logika bisnis, menerima repository interface
router.py          APIRouter(route_class=WrappedRoute)
depedencies.py     get_<domain>_repository, get_<domain>_service
```

Ejaan `depedencies.py` salah tetapi konsisten di semua domain; domain baru ikut ejaan itu. Domain: base, cities, schools, users, classrooms, contents, quizz, jobs, chatbot, otp. Template acuan: `contents/`.

`app/core/`: `config` (settings), `db` (Base, get_db), `security` (`Roles(Role.TEACHER)`), `response` (`Response[T]`, `COMMON_*_RESPONSES`), `route` (`WrappedRoute`), `exceptions` (`AppException` turunan), `taskiq`, `redis`, `model_registry`.

## Pola

- Router: `response_model=Response[T]`, `route_class=WrappedRoute`, otorisasi lewat `Roles(...)`, service lewat `Depends`.
- Error: lempar turunan `AppException` (`NotFoundException`, `ForbiddenException`, `BadRequestException`), jangan `HTTPException` baru.
- Tulis DB lewat `async with self.db.begin()` di service.
- Pekerjaan berat (MinerU, generate quiz, embedding) lewat task taskiq di `app/tasks/`, bukan di request handler. Fungsi ai-services sinkron, dipanggil dengan `asyncio.to_thread`.
- Impor ai-services berbasis paket (`from quizzer import ...`, `from common import ...`) setelah `app.utils.paths.setup()`.

## Migrasi

Model baru wajib didaftarkan di DUA tempat: `app/core/model_registry.py` dan impor eksplisit di `migrations/env.py`. Lalu `uv run alembic revision --autogenerate -m "<pesan>"` dari `backend/`, tinjau file hasil, baru `upgrade head`. Lihat skill `/alembic-migration`.

## Kontrak API

Kontrak API ada di koleksi Postman "Lydera" (cloud). Endpoint berubah: jalankan `/api-contract-sync`, yang memperbarui koleksi lewat konektor Postman setelah persetujuan user. Dokumentasi interaktif juga tersedia di `/docs` (OpenAPI FastAPI). Berkas Postman lama di repo sudah dihapus dari worktree.

## Catatan

`backend/uploads/` gitignored. `app/main.py` memasang `/static/annotations` dari `settings.OUTPUT_DIR`.
