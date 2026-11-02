# Planning

Tempat backlog dan roadmap. Satu berkas per topik: [backlog.md](backlog.md) (rencana dan item menunggu), [findings.md](findings.md) (temuan perilaku).

Item yang siap dikerjakan dipindah menjadi spec di [../specs/](../specs/) lewat `/feature-spec`.

Utang teknis yang sudah diketahui:
- Tes pytest untuk fungsi murni ada di `ai-services/tests/` dan `backend/tests/` (`uv run pytest -q`); belum ada linter atau formatter.
- Frontend Flutter belum dimulai.
- Kontrak API kini di koleksi Postman "Lydera" (cloud) dan OpenAPI di `/docs`. Berkas Postman lama dan `POSTMAN_API_LIST.md` terhapus dari worktree tetapi masih tercatat di git; putuskan dibuang permanen (`git rm`) atau dipulihkan.
- Koleksi Postman "Lydera" terakhir diubah 2026-09-14; kemungkinan tertinggal dari router saat ini. Jalankan `/api-contract-sync` untuk audit pertama.
- `alembic` migrasi awal `7687613b2cdc` bernama "membuat table chatbot" tetapi membuat hampir seluruh skema; nama menyesatkan.
- Nama berkas `depedencies.py` dan domain `quizz` salah eja tetapi dipakai konsisten.
- Berkas `.codex/` masih tercatat di git padahal ada di `.gitignore`.
