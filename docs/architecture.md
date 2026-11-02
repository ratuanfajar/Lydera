# Arsitektur

## Batas tanggung jawab

| Bagian | Bertanggung jawab atas | Tidak boleh |
|---|---|---|
| `ai-services/` | Ekstraksi PDF (MinerU), anotasi rumus/tabel/gambar, generate dan validasi soal (Quizzer), analisis jawaban (Evaluaizer), RAG tanya jawab (Clarifier). Fungsi sinkron, murni komputasi | Menyentuh database |
| `backend/` | Satu-satunya penulis DB, API, autentikasi/otorisasi, validasi keluaran AI, orkestrasi pekerjaan async | Memanggil LLM di luar `ai-services/` |
| `frontend/` | Seluruh presentasi: font, paginasi, navigasi heading, semantics TalkBack | Menafsirkan LaTeX; teks siap-baca datang dari backend |

Aturan emas: MLLM, lalu JSON tervalidasi, lalu backend, lalu DB. Tidak ada jalur MLLM langsung ke DB. Guru memvalidasi sebelum konten sampai ke siswa.

## Data inti

`module` (dibuat guru) memiliki banyak `chapter`; `chapter` memiliki banyak `block`. Kolom penting `block`: `block_type`, `reading_order` (per bab, bercelah kelipatan 10), `readable_text` (teks siap-TalkBack), `source_markup` (bentuk asli, mis. LaTeX atau HTML tabel), `review_priority`, `image_file`, `image_kind` (jenis gambar hasil klasifikasi Annoter), `ringkasan` dan `tabel` (khusus blok tabel: ringkasan dan tabel terstruktur untuk mode ringkasan dan mode telusur, [ADR 0008](adr/0008-tabel-dua-mode-baca.md)). Identitas modul dan bab ditetapkan guru secara eksplisit, bukan ditebak dari nama file.

Domain backend lain: users (guru, siswa), schools, cities, classrooms, quizzer (`soal`, `soal_opsi`, `soal_langkah`, `soal_stimulus`), evaluaizer, clarifier (`chapter_kb`, `block_embedding` dengan pgvector, `chat_session`, `chat_message`), jobs, otp.

## Alur Annoter

```
Guru upload PDF bab (pilih bagian body dari preview)
  -> backend memotong PDF, membuat Job, antre task taskiq
  -> run_mineru per window halaman (batch)
  -> preprocess: content_list.json menjadi blok ter-route
  -> annotate: teks/heading verbatim; rumus, tabel, gambar lewat MLLM (paralel, di-cache)
     gambar: klasifikasi 3 percobaan (tanpa konteks, dengan konteks, penentu akhir); dekoratif dilewati;
     selain itu dideskripsikan dengan prompt per jenis; jenisnya disimpan sebagai blocks.image_kind
  -> backend ingest_annotated_json: block ke PostgreSQL
  -> guru review per blok, feedback memicu regenerasi blok itu saja
  -> rilis ke siswa
```

## Alur Quizzer

```
block satu bab (DB) -> segment (per heading) -> context (ringkas) -> generate (satu soal per segmen)
  -> validate (jawab ulang independen oleh model keluarga lain) -> backend simpan soal
  -> guru validasi: LOTS diedit langsung, HOTS lewat feedback + regenerasi cluster
```

## Alur Chatbot

Blok bab di-embed (`text-embedding-3-large`, 3072 dimensi) ke `block_embedding`, bersama indeks kata kunci (`lexical_tsv`) dan bentuk kanonik rumus (`formula_norm`). Pertanyaan siswa melewati pencarian hibrida (vektor, kata kunci, rumus persis, digabung RRF), scope gate, grader, lalu agen (jawaban dikembalikan sebagai bacaan `message` dan tampilan `message_markup` berisi LaTeX) dengan satu alat eksternal terbatas (`search_oer`, enam host OER kurasi, skor minimal 0,6) dan sitasi yang diverifikasi. Cache query dan riwayat di Redis.

## Runtime

Satu image Docker (`Dockerfile`) memuat `backend/` dan `ai-services/`. API: uvicorn. Pekerjaan berat: worker taskiq dengan broker Redis. Deploy lewat tag git; lihat [runbooks/deploy-rollback.md](runbooks/deploy-rollback.md).
