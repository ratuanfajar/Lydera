# Backlog

Item yang siap dikerjakan dipindah menjadi spec lewat `/feature-spec`. Temuan perilaku ada di [findings.md](findings.md).

## Terencana

| Item | Status | Catatan |
|---|---|---|
| Soal dengan rumus LaTeX dan tabel (Fase A) | selesai, spec [0002](../specs/0002-soal-dengan-rumus-tabel-dan-gambar.md) | Rendering LaTeX dan tabel menunggu frontend |
| Tabel dua mode baca (telusur sel dan ringkasan) | selesai di backend dan AI, spec [0003](../specs/0003-tabel-dua-mode-baca.md) | UI menunggu frontend dan prototipe semantik tabel di TalkBack; tabel lama di DB belum punya ringkasan (perlu hitung ulang) |
| Gambar buatan LLM sebagai stimulus (Fase B) | ditahan (rencana di spec 0002) | Prasyarat: Fase A, frontend mampu merender, sampel dicek manual |
| Evaluaizer: justifikasi berpoin dari letak kesalahan | selesai, spec [0004](../specs/0004-evaluaizer-justifikasi-berpoin.md) | F-006, F-007, F-015, C-002 tertutup; tampilan guru (kesalahan umum) belum ada |
| Clarifier: hybrid RAG, OER saja, skor Tavily 0,6 | selesai, spec [0005](../specs/0005-clarifier-pencarian-hibrida-dan-sumber-oer.md), ADR [0010](../adr/0010-clarifier-pencarian-hibrida-dan-sumber-oer.md) | F-003, F-008, F-014, F-049, C-003, C-004 tertutup; F-048 (cuplikan sumber `murid.` tipis) terbuka; migrasi `c3d97c01e878` dan reindex baru di DB dev |
| Clarifier: rumus tampil normal dan bacaan narasi | selesai di backend dan AI, spec [0006](../specs/0006-clarifier-rumus-tampil-dan-bacaan.md) | Rendering LaTeX menunggu frontend; migrasi `0d3e13679f93` baru di DB dev |
| Prompt grafik dan teks di gambar Annoter | teruji terbatas (bab 1 sampel, 4 grafik) | F-029; perlu bab lain untuk grafik jenis lain |

## Menunggu persetujuan user

- Sinkron Postman sudah dilakukan untuk perubahan API Quizzer sampai Fase A.
- Menerapkan migrasi ke database selain dev.
- Deploy: tambahkan `app.tasks.evaluaizer_tasks` ke perintah worker VPS; jalankan migrasi `cb1cb0782cef`, `c3d97c01e878`, dan `0d3e13679f93`, lalu reindex semua bab (Clarifier) setelah deploy.

## Masalah yang diketahui

- Juri `DeepSeek-V3.2` tidak tersedia di resource Azure (F-031).
- Seed `cp.cp_text` hanya satu kata (F-032).
- Feedback regenerasi tanpa panjang minimal (F-036, ranah backend).
