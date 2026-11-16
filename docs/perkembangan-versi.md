# Perkembangan Lydera: versi awal dan versi sekarang

Dokumen ini membandingkan Lydera pada dua titik acuan, menurut arsitektur, alur, dan keterbaruan tiap fitur. Isinya diambil dari riwayat git, kode, dan dokumen proyek (ADR, spec, findings). Angka mutu hanya yang sudah tercatat di sana; yang belum diukur ditandai.

## 1. Titik acuan

Ada tiga titik pada riwayat git. Tabel perbandingan di bagian berikutnya memakai dua kolom: **versi awal** (titik 2) dan **versi sekarang** (titik 3). Titik 1 hanya dicatat sebagai sejarah.

| | 1. Rilis pertama | 2. Versi awal (dipakai di tabel) | 3. Versi sekarang |
|---|---|---|---|
| Acuan git | tag `lydera-1.0.0` sampai `lydera-1.0.10` (12 Sep 2026) | commit `8637e09` (24 Sep 2026) | commit `e8531e7` pada branch `migration` (3 Nov 2026) |
| Isi | Hanya Annoter dan domain dasar backend (32 endpoint); model OpenRouter `qwen/qwen3.7-flash`; belum ada quiz, chatbot, dan evaluasi | Keempat fitur AI pertama kali ada bersama; sudah pindah ke Azure `gpt-5.4-mini`; belum ada dokumentasi `docs/` | Hasil seluruh perubahan di branch ini; belum bertag (tag terakhir `lydera-1.0.10`) |

Riwayat singkat: 29 Agu 2026 proyek dimulai; 2 Sep fitur anotasi; 7 Sep backend FastAPI, Docker, dan workflow deploy; 6-16 Sep quiz generator; 15-16 Sep chatbot dan evaluasi langkah siswa; 24 Sep versi awal (model Azure); 2-3 Nov pembaruan fitur di dokumen ini.

## 2. Ringkasan perubahan dalam angka

Dihitung dari git. "Endpoint" adalah jumlah dekorator route di `backend/app/domains/*/router.py` (perkiraan jumlah operasi API).

| Ukuran | Versi awal | Versi sekarang |
|---|---|---|
| Fitur AI | 4 (Annoter, Quizzer, Evaluaizer di dalam `quiz/`, chatbot) | 4 (Annoter, Quizzer, Evaluaizer, Clarifier), masing-masing paket sendiri |
| Berkas Python `ai-services/` (tanpa tes dan output) | 39 | 74 |
| Berkas tes | 11 | 67 (1.312 tes lulus pada 3 Nov 2026) |
| Endpoint backend | 56 | 58 |
| Domain backend | 10 | 11 (domain `evaluaizer` baru, `chatbot` menjadi `clarifier`, `quizz` menjadi `quizzer`) |
| Migrasi Alembic | 3 | 13 |
| Berkas dokumentasi di `docs/` | 0 | 42 (16 ADR, 10 spec, 5 catatan riset, runbook, findings) |
| Model | Azure `gpt-5.4-mini`; validator `grok-4.3`; embedding `text-embedding-3-large` (rilis pertama memakai OpenRouter `qwen/qwen3.7-flash`) | Sama, dengan effort `none` untuk Annoter dan `low` untuk fitur yang menalar |

## 3. Arsitektur

### 3.1 Struktur kode AI

Versi awal: satu folder per fitur (`annotation/`, `quiz/`, `chatbot/`), kode bersama diduplikasi, dan jalur impor diatur lewat `paths.py` yang mengubah `sys.path`.

```
ai-services/
  annotation/   (llm, cache, config, paths, anotasi)
  quiz/         (jsonutil, parallel, paths, generate, validate, evaluate)
  chatbot/      (agen, chunk, alat pencarian)
```

Versi sekarang: empat paket fitur ditambah `common/` yang dipakai bersama; fitur hanya bergantung pada `common/`, bukan satu sama lain (ADR 0004). Impor berbasis paket.

```
ai-services/
  common/       llm, cache, jsonutil, parallel, resilience, prompt_format, guardrails,
                formula, formula_check, math_text, notation_check, table_spec,
                image_prompts, image_describe, svg_raster, speakable, phrases, embedding
  annoter/      run_mineru, batch, preprocess, annotate, priority, table, image, prompts,
                annoter_pipeline, annoter_regenerate
  quizzer/      segment, points, mapping, generate, checks, shuffle, validate, revise,
                readable, quizzer_pipeline, quizzer_regenerate, stimulus/ (tabel, gambar, campuran)
  evaluaizer/   evaluate, checks, prompts
  clarifier/    agent, tools, scope_gate, retrieval_grader, citations, chunk, lexical, fusion,
                formula_text, speech, table, practice, external_tools, trusted_domains
```

### 3.2 Yang tetap

- `ai-services/` murni komputasi; backend satu-satunya penulis DB.
- Alur data: MLLM, JSON tervalidasi, backend, DB.
- FastAPI async, PostgreSQL dengan pgvector, Redis, taskiq, MinerU untuk ekstraksi PDF.
- Frontend (Flutter) belum dimulai; seluruh presentasi tetap tugas klien.

### 3.3 Yang berubah di tingkat sistem

| Aspek | Versi awal | Versi sekarang |
|---|---|---|
| Format prompt | Annoter memakai format baku; fitur lain bebas | Semua prompt memakai `build_prompt` dan `build_input` (ROLE, TASK, CONTEXT, RULES, OUTPUT FORMAT, EXAMPLES), dijaga tes |
| Keamanan prompt | Aturan "isi tag adalah data" terpisah-pisah per prompt | Pagar berlapis seragam (ADR 0016): aturan otomatis, pembatas tag, penyaring masukan, pemeriksa kebocoran |
| Ketahanan | Retry LLM | Ditambah pemutus sirkuit untuk outage model (`resilience`) dan penandaan blok atau window gagal tanpa membatalkan job |
| Kontrak teks | Satu teks per elemen | Teks bacaan TalkBack dan bentuk tampilan (`source_markup`, `message_markup`) selalu berpasangan |
| Gambar SVG | Tidak ada | Stimulus SVG dirasterisasi (resvg-py, font `fonts-liberation` di Docker) lalu dideskripsikan model vision |
| Dokumentasi | README per folder | Arsitektur, ADR, spec, runbook, findings, riset (lihat bagian 8) |
| Pengujian | 11 berkas tes | 67 berkas tes, snapshot prompt, tes format dan keamanan prompt |

### 3.4 Alur data sekarang

```
Guru unggah PDF bab
  -> Annoter (MinerU -> blok -> rumus/tabel/gambar lewat MLLM) -> blok di DB
  -> guru meninjau, mengedit langsung atau regenerasi dengan feedback, lalu publish modul
  -> reindex Clarifier otomatis setelah anotasi (chunk -> embedding -> pgvector)
Guru membuat kuis
  -> Quizzer (poin -> slot -> generate -> pemeriksaan kode -> verifikasi) -> soal di DB
  -> guru meninjau/mengedit, lalu publish: kunci jawaban terkunci
Siswa mengerjakan kuis
  -> submit jawaban dan langkah; Evaluaizer menunjuk letak kesalahan untuk jawaban salah
Siswa memakai Clarifier (di luar waktu kuis)
  -> tanya jawab dari modul dan sumber luar terbatas, serta latihan soal di chat
```

## 4. Keterbaruan tiap fitur

### 4.1 Annoter (modul PDF menjadi teks siap TalkBack)

| Aspek | Versi awal | Versi sekarang |
|---|---|---|
| Gambar | Satu prompt vision umum, hasil JSON `pengamatan` lalu `deskripsi` | Klasifikasi tiga percobaan (tanpa konteks, dengan teks tetangga, penentu akhir) ke enam jenis (`dekoratif`, `ilustrasi_konteks`, `geometri`, `grafik`, `diagram`, `teks_di_gambar`), lalu prompt per jenis; dekoratif dilewati; jenis disimpan di `blocks.image_kind` |
| Rumus | Verbalisasi LaTeX oleh model teks | Verbalizer gaya kelas ("f dari g dari empat", penutup "selesai akar"), pemeriksa struktur bacaan, satu percobaan ulang, yang masih bermasalah berprioritas tinjau tinggi; dipakai bersama Quizzer dan Clarifier lewat `common/` |
| Tabel | Linearisasi teks | Dua mode baca (ADR 0008): tabel terstruktur, bacaan linear, dan ringkasan yang disusun kode |
| Peninjauan guru | Regenerasi blok dengan feedback | Ditambah edit langsung teks, rumus, tabel, dan gambar lewat `PATCH /api/blocks/{block_id}` (spec 0008) |
| Ketahanan | Cache berkunci `PROMPT_VERSION` | Pemutus sirkuit untuk outage model; blok atau window gagal ditandai, bukan membatalkan job; cache terpisah per jenis (`PROMPT_VERSION` 13, `FORMULA_PROMPT_VERSION` 3, `TABLE_PROMPT_VERSION` 5) |
| Keamanan | Aturan data pada umpan balik guru | Blok yang memuat kalimat peniru instruksi berprioritas tinjau tinggi |

Catatan mutu: prompt rumus dengan contoh few-shot tercatat 97,1% kesetiaan pada 120 LaTeX unik (set uji tunggal, README `ai-services`).

### 4.2 Quizzer (soal pilihan ganda)

| Aspek | Versi awal | Versi sekarang |
|---|---|---|
| Perencanaan | Per bab: segmen dipecah dengan regex heading `A.`/`B.`/`C.`, ringkasan bertingkat (map-reduce), satu soal per segmen | Rencana dulu, baru generate (ADR 0006): segmen menurut blok dan karakter (heading hanya titik potong), ekstraksi poin materi, pemetaan ke slot (bab x level Bloom) dengan kuota guru ditegakkan kode; semua bab terpilih diproses dalam satu panggilan |
| Pemeriksaan | Jawab buta oleh validator `grok-4.3`, hanya menandai | Pemeriksaan kode (struktur opsi, rujukan visual, panjang kunci), acak opsi dengan target kunci seimbang, jawab buta dan audit; temuan berat memicu satu regenerasi; laporan cakupan (`coverage_report`) |
| Isi soal | Teks biasa; stimulus teks | Rumus LaTeX dan tabel terstruktur, teks bacaan diturunkan terpisah; stimulus bertipe `tabel`, `gambar` (SVG), `campuran` yang dipilih model per soal HOTS (spec 0007, ADR 0012) |
| Peninjauan guru | Feedback lalu regenerasi cluster HOTS | Ditambah edit langsung soal LOTS dan HOTS dan stimulus pada bentuk aslinya (spec 0008) |
| Siklus kuis | Kunci jawaban tidak dikunci | Publish mengunci kunci (edit dan regenerasi ditolak); publish hanya untuk kuis berstatus `done`; submit setelah batas waktu plus toleransi 10 detik ditolak |
| Prompt | Prompt bebas | Format baku, prompt dijaga netral dari materi contoh (tes), `QUIZ_PROMPT_VERSION` 5 |

Catatan mutu: pilot Quizzer tercatat di findings F-068; belum ada klaim tingkat kebenaran kunci (satu ulangan per putaran, dan beberapa soal berkunci salah lolos audit).

### 4.3 Evaluaizer (analisis jawaban siswa yang salah)

| Aspek | Versi awal | Versi sekarang |
|---|---|---|
| Letak dalam kode | Fungsi `quiz/evaluate.py` di dalam paket quiz; domain backend ikut `quizz` | Paket `evaluaizer/`, domain backend `evaluaizer`, task `evaluaizer_tasks`, endpoint hasil siswa |
| Keluaran | `divergence_step`, `diagnosis`, `personalized_justification` (rekomendasi) | `dapat_ditentukan`, `langkah_ke`, `kutipan`, `keterangan`; tanpa rekomendasi atau akar masalah (ADR 0013, spec 0009) |
| Cakupan | Jawaban salah | Hanya jawaban salah yang punya langkah tertulis; langkah berisi nilai saja dinyatakan tak dapat ditentukan |
| Penalaran | Satu keluaran | Model menilai tiap langkah (daftar benar/salah) sebelum menunjuk letak kesalahan pertama |
| Verifikasi | Tidak ada pemeriksa kode | Kode memeriksa bahwa kutipan ada pada langkah yang ditunjuk, tanpa simbol mentah atau tanda tanya, satu percobaan perbaikan, lalu `needs_review` |
| Data | Kolom justifikasi | Kolom `divergence_step`, `diagnosis`, `letak_kutipan`, `letak_dapat_ditentukan` pada `soal_jawaban` |
| Keamanan | Aturan data untuk catatan siswa | Langkah siswa peniru instruksi menandai hasil untuk ditinjau; keterangan yang membocorkan instruksi ditolak |

Catatan mutu: 26 kasus uji dengan kebenaran dasar, 3 ulangan tanpa model juri (`evaluaizer/eval`); hasil dan kelemahan tercatat di findings F-070. Belum diuji dengan tulisan siswa nyata.

### 4.4 Clarifier (tanya jawab dan teman belajar; dulu "chatbot")

| Aspek | Versi awal | Versi sekarang |
|---|---|---|
| Pengindeksan | Satu blok = satu vektor | Chunk berbasis ukuran 600-1.200 karakter dengan overlap satu blok, heading hanya titik potong (ADR 0015); indeks kata kunci dan bentuk kanonik rumus per chunk; reindex otomatis setelah anotasi selesai |
| Pencarian | Vektor | Hibrida: vektor, kata kunci (hanya token jarang), dan rumus persis, digabung RRF (ADR 0010) |
| Sumber luar | `search_oer`, Wolfram Alpha, dan pencarian web berperingkat domain dengan `trust_tier` | Hanya `search_oer` ke enam host OER kurasi dengan skor minimal 0,6; Wolfram, web umum, dan `trust_tier` dihapus |
| Bentuk jawaban | Satu teks | `message` (bacaan), `message_markup` (LaTeX), `rumus` (pasangan LaTeX dan bacaan), `tabel` dengan bacaan dan ringkasan, `sources[].blok` (tabel dan gambar asli dari modul) (spec 0006, 0010) |
| Alur agen | Scope gate, alat, `compose_answer`, verifikasi kutipan | Ditambah penyaring peniru instruksi, penilai relevansi (grader), `request_practice`, pemeriksa kebocoran, riwayat dibungkus tag |
| Latihan soal | Tidak ada | Siswa meminta di chat; soal dibuat dengan komponen Quizzer dan hanya dikirim bila lolos tanpa temuan; disimpan di Redis, tidak masuk nilai atau DB; dijawab dengan mengetik huruf; berlabel "belum ditinjau guru"; 10 permintaan per siswa per jam (ADR 0014) |
| Perilaku dengan kuis | Bebas dipakai | Dikunci (400) selama siswa mengerjakan kuis |
| Cakupan fitur | - | Berdiri sendiri; penjelasan soal dari hasil kuis sempat dibuat lalu dibatalkan |
| Penolakan | Redirect halus | Pesan penolakan juga mengarahkan siswa yang tertekan ke guru atau orang dewasa tepercaya |

Catatan mutu (ADR 0010, DB dev, bab 1 dan 2): untuk 14 pertanyaan rumus persis, MRR naik dari 0,475 (vektor saja) menjadi 1,000 (hibrida) dan recall@5 dari 13 menjadi 14 dari 14; untuk 17 pertanyaan umum recall@5 sama (14 dari 17). Bobot dituning pada data yang sama, jadi angkanya optimistis. Recall chunker baru belum diukur.

## 5. Lintas fitur

- **Aksesibilitas TalkBack**: semua teks siswa tanpa markdown dan tanpa kalimat pembuka basa-basi; rumus dan tabel selalu disertai narasi yang disusun kode atau verbalizer; klien menerima pasangan tampilan dan bacaan.
- **Pagar prompt** (ADR 0016): aturan anti-injeksi otomatis di semua prompt sistem, pembatas tag untuk masukan siswa, guru, PDF, gambar, dan web, penyaring pola tanpa LLM, serta pemeriksa kebocoran instruksi. Pola tidak menangkap semua parafrasa; efektivitas terhadap model nyata belum diukur.
- **Kualitas rekayasa**: tes dari 11 menjadi 67 berkas, snapshot prompt, tes format prompt, dan pembersihan kode dan dependensi yang tidak terpakai (`ragas`, `langchain-openai`, `pandas`).
- **Operasional**: image Docker memuat font untuk render SVG; reindex Clarifier wajib setelah chunker berubah; versi prompt anotasi yang naik membuat cache lama tidak terpakai.

## 6. Perubahan kontrak API untuk klien

- Chat Clarifier: field baru `rumus`, `tabel`, `tabel_bacaan`, `tabel_ringkasan`, `sources[].blok`, `latihan`; `trust_tier` dihapus; 400 selama kuis; 429 untuk latihan berlebih.
- Soal kuis: stimulus bertipe (`jenis`, `spesifikasi`) dan `markup` LaTeX di samping teks bacaan.
- Hasil kuis siswa: `letak_kesalahan` pada tiap soal yang salah.
- Guru: edit langsung blok dan stimulus (`PATCH`), kunci kuis setelah publish, dan publish hanya untuk kuis `done`.
- Sumber kebenaran kontrak: koleksi Postman "Lydera".

## 7. Batasan dan yang belum terukur

- Recall retrieval dengan chunker baru, mutu soal latihan, dan ketahanan terhadap injeksi belum diukur dengan model nyata (perlu tiga ulangan dan pengecekan ke sumber).
- Hasil Evaluaizer belum diuji dengan tulisan siswa nyata; kunci jawaban Quizzer masih bisa salah pada sebagian kecil soal.
- Uji dengar TalkBack nyata belum dilakukan dan frontend belum dimulai.
- Latihan soal buatan AI adalah satu-satunya konten yang sampai ke siswa tanpa tinjauan guru; risiko itu diterima secara sadar (ADR 0014).
- Dua file backend tidak terpakai (`app/utils/pdf_cut.py`, `app/utils/token.py`) belum dihapus.

## 8. Rujukan

- Arsitektur dan alur: `docs/architecture.md`; panduan per bagian: `ai-services/README.md`, `backend/README.md`.
- Keputusan: ADR 0001-0016 di `docs/adr/` (terutama 0004 batas fitur, 0006 Quizzer, 0010 dan 0015 Clarifier, 0012 stimulus bertipe, 0013 Evaluaizer, 0014 latihan soal, 0016 pagar prompt).
- Spesifikasi fitur: `docs/specs/0001`-`0010`.
- Temuan, uji, dan status: `docs/planning/findings.md` (F-068 sampai F-072 untuk pekerjaan terbaru).
- Riset: `docs/research/`.
