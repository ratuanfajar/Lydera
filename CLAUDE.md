# Lydera

Aplikasi mobile pembelajaran matematika untuk siswa tunanetra dan guru SLB. Empat fitur AI: **Annoter** (modul PDF menjadi teks siap-TalkBack), **Quizzer** (soal pilihan ganda dari modul teranotasi), **Evaluaizer** (analisis jawaban siswa yang salah), **Clarifier** (tanya jawab RAG dari modul yang sama). Output AI divalidasi guru sebelum sampai ke siswa; satu-satunya pengecualian adalah latihan soal buatan AI di chat Clarifier (ADR 0014).

## Peta repo

| Folder | Isi | Panduan |
|---|---|---|
| `backend/` | FastAPI async, SQLAlchemy, PostgreSQL + pgvector, Alembic, Redis + taskiq | `backend/CLAUDE.md` |
| `ai-services/` | `common/`, `annoter/` (MinerU + MLLM), `quizzer/`, `evaluaizer/`, `clarifier/`. Komputasi murni | `ai-services/CLAUDE.md` |
| `frontend/` | Flutter (belum dimulai) | `frontend/CLAUDE.md` |
| `docs/` | arsitektur, ADR, spec, runbook, planning | `docs/README.md` |
| `data/` | PDF modul sumber (gitignored) | |

Satu proyek uv di root (`pyproject.toml`, `uv.lock`), dipakai bersama `backend/` dan `ai-services/`. Python 3.12.

## Perintah

```
uv sync
cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
cd backend && uv run alembic upgrade head
cd backend && uv run taskiq worker app.core.taskiq:broker app.tasks.mineru_tasks app.tasks.quiz_tasks app.tasks.process_exam_review_tasks app.tasks.chatbot_tasks app.tasks.progress_tasks app.tasks.email_tasks app.tasks.file_tasks app.tasks.evaluaizer_tasks
```

Jika uvicorn gagal dengan `Failed to canonicalize script path`, pakai `uv run python -m uvicorn ...`. Env: `backend/.env` dan `ai-services/.env` (contoh: `.env.example`). Tes: `uv run pytest -q` dari root (tes fungsi murni; tanpa DB, jaringan, atau LLM nyata). Belum ada linter atau formatter.

## Aturan keras

1. `ai-services/` tidak pernah menyentuh database. Backend satu-satunya penulis DB.
2. Alur data: MLLM, lalu JSON tervalidasi, lalu backend, lalu DB. Jangan MLLM langsung ke DB.
3. Jangan membaca atau mencetak isi `.env`. Skrip boleh memuatnya saat runtime.
4. Jangan `git commit` atau `git push`. User yang commit.
5. Ubah prompt anotasi berarti naikkan `PROMPT_VERSION` di `ai-services/common/config.py` (prompt rumus dan tabel memakai `FORMULA_PROMPT_VERSION` dan `TABLE_PROMPT_VERSION`).
6. Pilih model dengan urutan prioritas: kualitas, lalu biaya. Keluarga GPT dibatasi sampai 5.4; model non-GPT boleh dibandingkan.
7. Teks untuk siswa harus bisa dibaca TalkBack: tanpa markdown, tanpa bintang, tanpa kalimat pembuka basa-basi.
8. Gaya kode: tanpa komentar, tanpa docstring kecuali 1 baris untuk perilaku yang tidak terlihat dari signature. Nama jelas, fungsi kecil. Tidak ada file scratch di repo.
9. Jangan klaim hasil eval dari satu kali jalan. Juri LLM berisik; ulang 3 kali dan cek ke sumber asli.

## Konvensi

- Istilah domain berbahasa Indonesia dipertahankan: `soal`, `jawaban`, `langkah`, `modul`, `bab`, `fase`, `cp`.
- Respons API dibungkus `Response[T]` (`message`, `data`); error berbentuk `detail` + `errors`.
- Commit singkat, huruf kecil, imperatif (`fix review exam`).
- Deploy: push tag `lydera-*`, `vX.Y.Z`, atau `X.Y.Z` memicu build GHCR lalu deploy VPS (`docs/runbooks/deploy-rollback.md`).

## Skill dan agent

Panggil sendiri lewat tool Skill/Agent saat pemicunya muncul; jangan menunggu user mengetik. Sebut skill yang dipakai dalam satu kalimat. Jika ragu antara dua, pilih yang lebih spesifik. Sebelum menutup tugas, periksa tabel ini (migrasi, Postman, `PROMPT_VERSION`, review).

| Pemicu | Skill / agent |
|---|---|
| Fitur baru atau perubahan perilaku | `feature-spec` |
| Entitas, tabel, atau router baru | `new-backend-domain`, `alembic-migration` |
| Model SQLAlchemy berubah | `alembic-migration` |
| Prompt atau parameter anotasi berubah, hasil anotasi salah | `annotation-prompt-change` |
| Endpoint, request, atau response berubah | `api-contract-sync` |
| Pilih, ganti, atau bandingkan model; benchmark | `model-eval` |
| Perlu fakta dari paper, dokumentasi library, harga, kuota | `research` (paralel: agent `researcher`) |
| Mencari opsi, trade-off, arah desain | `brainstorm` |
| Diskusi mencapai kesimpulan | `capture-decision` |
| Kode backend atau ai-services selesai diubah | agent `lydera-reviewer` |
| Logika non-trivial baru | agent `test-writer` |
| Teks siswa, anotasi, soal, atau UI berubah | agent `a11y-reviewer` |

Hook proyek (`.claude/hooks/reminders.py`) mengirim pengingat berdasarkan prompt dan file yang diedit; pengingat itu hanya dorongan, keputusan memakai skill tetap di Claude.

## Riset dan brainstorming

- Dokumentasi library dari Context7 (`resolve-library-id`, `query-docs`), bukan ingatan. Paper dari alphaXiv. Harga dan kuota Azure dari tool Azure.
- Kutip sumber dan tanggal akses. Pisahkan fakta dan inferensi. Jangan memutuskan arsitektur dari satu sumber.
- Hasil yang layak diingat disimpan di `docs/research/` (setelah user setuju); keputusan menjadi ADR di `docs/adr/`.
