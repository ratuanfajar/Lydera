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
  -> guru review per blok: edit langsung (teks, rumus, tabel, gambar) atau feedback memicu regenerasi blok itu saja (spec 0008)
  -> rilis ke siswa
```

## Alur Quizzer

```
blok tiap bab (DB) + CP + kuota HOTS/LOTS dari guru
  -> segment (blok dan karakter, heading hanya titik potong) -> points (poin materi, LLM) -> mapping (slot bab x level, kuota ditegakkan kode)
  -> generate (satu soal per slot; LOTS tanpa stimulus, HOTS dengan stimulus teks, tabel, gambar SVG, atau campuran pilihan model)
  -> checks (kode) -> shuffle -> validate (jawab buta + audit oleh model keluarga lain; temuan berat memicu satu regenerasi)
  -> backend simpan soal -> guru validasi: edit langsung soal dan stimulus, atau feedback + regenerasi cluster HOTS (spec 0008)
  -> guru publish: kunci jawaban terkunci (edit dan regenerasi ditolak) dan kuis dapat dikerjakan siswa
```

Bentuk stimulus dan kontrak render klien: spec 0007 dan ADR 0012.

## Alur Evaluaizer

Hanya jawaban salah yang punya langkah tulisan siswa dianalisis. Model membandingkan langkah siswa dengan langkah kunci yang sudah disetujui guru dan hanya menunjuk letak kesalahan pertama (`langkah_ke`, `kutipan`, `keterangan`); kode memeriksa bahwa kutipan benar-benar ada pada langkah itu. Spec 0009 dan ADR 0013.

## Alur Clarifier

Clarifier adalah satu chatbot asisten belajar yang berdiri sendiri: tidak membahas kuis dan tidak punya halaman terpisah. Selama siswa mengerjakan kuis, Clarifier dikunci untuk siswa itu.

Blok bab di-embed (`text-embedding-3-large`, 3072 dimensi) ke `block_embedding` per chunk (dikemas menurut ukuran karakter, ADR 0015), bersama indeks kata kunci (`lexical_tsv`) dan bentuk kanonik rumus (`formula_norm`). Pengindeksan dijalankan worker begitu anotasi satu bab selesai, atau manual lewat endpoint reindex. Pertanyaan siswa melewati penyaring peniru instruksi, pencarian hibrida (vektor, kata kunci, rumus persis, digabung RRF), scope gate, grader, lalu agen dengan alat eksternal terbatas (`search_oer`, enam host OER kurasi, skor minimal 0,6) dan sitasi yang diverifikasi. Jawaban memuat bacaan `message`, tampilan `message_markup` (LaTeX), pasangan `rumus`, `tabel` opsional dengan bacaannya, dan blok tabel atau gambar asli dari modul. Cache query dan riwayat di Redis.

Latihan soal buatan AI hanya di antarmuka chat (ADR 0014): model memanggil `request_practice`, backend membuat soal dengan komponen Quizzer dan menyimpannya di Redis tanpa menulis DB, lalu siswa menjawab dengan mengetik huruf pilihan. Soal tidak ditinjau guru, tidak masuk nilai, dan dibatasi 10 permintaan per siswa per jam.

## Pagar prompt

Semua prompt dilindungi lapisan anti-injeksi bersama (ADR 0016): aturan otomatis di prompt sistem, pembatas tag untuk masukan tak tepercaya, penyaring pola, dan pemeriksa kebocoran di keluaran.

## Runtime

Satu image Docker (`Dockerfile`) memuat `backend/` dan `ai-services/`. API: uvicorn. Pekerjaan berat: worker taskiq dengan broker Redis. Deploy lewat tag git; lihat [runbooks/deploy-rollback.md](runbooks/deploy-rollback.md).
