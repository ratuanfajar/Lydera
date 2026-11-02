# 0001. Pipeline Quizzer: rencana dulu, lalu generate dan verifikasi

- Status: selesai (implementasi dan verifikasi 2026-10-27; Postman dan pytest menunggu persetujuan)
- Tanggal: 2026-10-27
- ADR terkait: [0006](../adr/0006-quizzer-plan-then-generate.md). Dasar: [research 0004](../research/0004-pipeline-quizzer-plan-then-generate.md)

## Masalah

Guru memilih beberapa bab dan jumlah soal HOTS dan LOTS per bab. Pipeline sekarang membuat satu soal langsung dari satu segmen (bagian di bawah heading `A.`, 14-22 ribu karakter, hanya 3 per bab) dan menyisakan enam kelemahan:

1. Tiap soal dibuat tanpa tahu soal lain: soal kembar dan konsep berulang tidak terkontrol.
2. Alokasi berurutan menurut segmen: segmen belakang tidak kebagian soal bila jumlah soal sedikit.
3. Satu soal gagal membatalkan seluruh job dan semua soal hilang.
4. Bab tanpa heading berpola `A.` membuat seluruh permintaan gagal, dan segmen `A.` terlalu besar untuk satu input.
5. Validator hanya menjawab ulang kunci; langkah dan kesimpulan yang salah lolos, padahal siswa dan Evaluaizer memakainya sebagai acuan.
6. Level Bloom dan panjang opsi tidak dikendalikan (Bloom exact-match sekitar 0,75; kunci = opsi terpanjang pada 46% soal).

Terdampak: guru (meninjau soal yang salah atau kembar) dan siswa tunanetra (mendengar justifikasi yang salah).

## Perilaku yang diharapkan

Alur per permintaan kuis (semua bab terpilih diproses bersama):

1. **Segmentasi** (kode). Tiap bab dipotong menjadi segmen berdasarkan blok dan jumlah karakter, tanpa bergantung pada pola heading. Blok disusun berurutan menjadi kelompok tak terpisah (heading ikut blok setelahnya; rumus, tabel, dan gambar ikut blok teks sebelumnya; contoh soal dan penyelesaiannya satu kelompok). Kelompok dikumpulkan sampai mencapai target sekitar 4.000 karakter; setelah itu boleh terus menambah kelompok sampai batas keras 8.000 hanya bila dalam rentang itu ada heading, dan potong tepat sebelum heading itu; bila tidak ada, potong di batas kelompok terdekat. Heading hanya memilih titik potong di antara kandidat. Tidak pernah memotong di dalam satu blok. Overlap 2 blok terakhir segmen sebelumnya ditambahkan sebagai konteks baca saja. Ekor kurang dari 1.000 karakter digabung ke segmen sebelumnya (segmen terakhir bisa melampaui 8.000 sampai 1.000 karakter), dan rantai blok tak terpisah yang melewati 1,5 kali batas keras dipotong paksa di batas blok. Blok pembuka (judul, Tujuan Pembelajaran, Pertanyaan Pemantik, Kata Kunci, Peta Konsep, Pengantar) tidak jadi sumber soal. Bab tanpa blok teks dilewati dan dilaporkan; bab lain tetap diproses.
2. **Ekstraksi poin** (LLM, per segmen, paralel, di-cache). Keluaran tiap poin: teks poin, jenis (`definisi`, `rumus`, `prosedur`, `konsep`, `miskonsepsi`, `perbandingan`, `aplikasi`), rentang `reading_order` sumber, dan kutipan pendek. Poin kembar dari segmen bertetangga digabung.
3. **Pemetaan** (LLM mengusulkan, kode memutuskan). Masukan: semua poin, CP tiap bab, dan kuota guru per bab. Level ditentukan kode dari kuota: LOTS dibagi merata ke C1-C3, HOTS ke C4-C5. LLM memilih poin untuk tiap slot (bab, level). Kode memvalidasi: jumlah persis kuota per bab dan level; kecocokan jenis poin dengan level (mis. C4 untuk `miskonsepsi`, `perbandingan`, `prosedur`; C5 untuk `perbandingan` dan `aplikasi`); satu poin paling banyak dipakai sekali, dipakai ulang hanya bila poin kurang dan dilaporkan; sebaran merata antar segmen. Kekurangan diisi pengisi deterministik. Bila poin terlalu banyak untuk satu panggilan, pemetaan dilakukan per bab.
4. **Generate** (LLM, satu panggilan per slot, paralel). Masukan: poin, teks sumber rujukan poin ditambah margin 3 blok, CP bab, level Bloom. Stimulus teks saja untuk C4 dan C5. Soal dan stimulus tanpa rujukan ke gambar, grafik, tabel, atau diagram; langkah dan kesimpulan tanpa huruf opsi.
5. **Pemeriksaan kode** setelah generate: tipe dan bentuk data (opsi A-D berupa teks, langkah berupa daftar teks), stimulus sesuai level (C4-C5 wajib, C1-C3 tidak boleh), rujukan visual (regex), simbol atau rumus mentah yang tidak diverbalisasi, soal yang mengulang isi stimulus, kunci jauh lebih panjang dari opsi lain (lebih dari 1,4 kali rata-rata opsi lain). Masalah yang ditemukan dikumpulkan sebagai koreksi.
6. **Acak urutan opsi** (kode) dengan target kunci seimbang per bab, lalu langkah dan kesimpulan dipetakan ulang (sudah ada).
7. **Verifikasi Grok dua langkah.** A: menjawab buta (sudah ada). B: audit dengan kunci dan justifikasi, keluaran JSON `langkah_valid`, `kesimpulan_konsisten`, `opsi_lain_benar`, `stem_ambigu`, `stimulus_dibutuhkan` (HOTS), `masalah`. Soal ditandai bila A tidak cocok, B menemukan masalah, atau ada opsi lain benar. Bloom bukan syarat lolos. Kegagalan infrastruktur validator (timeout, 429) juga hanya menandai soal untuk ditinjau. **Temuan verifier hanya menandai soal (`review_priority` tinggi dan `validation_notes`); soal tidak diubah otomatis.** Perubahan baru terjadi setelah guru meninjau dan memberi feedback (keputusan user).
8. **Perbaikan otomatis satu kali hanya untuk masalah dari pemeriksaan kode** (langkah 5, objektif dan tanpa Grok): soal diregenerasi sekali dengan daftar masalah sebagai koreksi. Anggaran per slot: paling banyak 2 generate, 1 jawab buta, 1 audit.
9. **Soal dengan masalah tersisa** (dari pemeriksaan kode setelah perbaikan, atau dari verifier) disimpan dengan `review_priority` tinggi dan `validation_notes` berisi masalahnya. Bila percobaan kedua error, kandidat valid terbaik dari percobaan sebelumnya yang disimpan.
10. **Tidak ada cek duplikat.** Guru yang menilai kemiripan antar soal (keputusan user: hemat biaya dan waktu). Poin tidak dipakai ulang dalam satu bab bila poin cukup, dan poin kembar antar segmen dibuang dengan kemiripan kata saat ekstraksi.
11. **Isolasi kegagalan.** Satu slot yang error (setelah retry) dicatat dan dilewati; slot lain tetap selesai dan disimpan. Job `done` bila minimal satu soal tersimpan, `failed` bila nol.
12. **Laporan cakupan** disimpan dan ditampilkan ke guru setelah selesai: per bab jumlah poin, poin terpakai, jumlah diminta vs dihasilkan, slot gagal beserta alasan, poin dipakai ulang, poin tak terpakai; ringkasan jumlah soal diperbaiki dan berprioritas tinggi. Tiap soal membawa `source_point`.

Deteksi keluaran terpotong: `common/llm.py` memeriksa `finish_reason`. Bila `length`, ulangi dengan batas token lebih besar sekali; ekstraksi yang masih gagal membagi segmen menjadi dua.

## Di luar cakupan

- Guru melihat atau mengedit kisi-kisi sebelum soal dibuat (keputusan user: tidak).
- Total soal lintas bab yang dibagi otomatis; guru tetap mengisi kuota per bab.
- Level C6 dan kalibrasi psikometri.
- Gambar jenis apa pun di soal dan stimulus (geometri, grafik, diagram, ilustrasi konteks, teks di gambar). Keterbatasan yang diterima: soal yang butuh gambar harus bisa dinyatakan lengkap dalam kata. Rumus LaTeX dan tabel dengan tampilan visual serta gambar buatan LLM ditunda ke spec 0002.
- Bloom sebagai syarat lolos verifikasi.
- Perubahan alur regenerasi guru (`quizzer_regenerate`), selain mungkin pemeriksaan rujukan visual (tindak lanjut terpisah).

## Perubahan data

Migrasi Alembic (lewat `/alembic-migration`, persetujuan user, hanya DB dev dari sesi ini):

- `soal.source_point` (Text, nullable).
- `quiz_requests.coverage_report` (JSONB, nullable).

Tanpa data lama yang dimigrasi; kolom kosong untuk kuis lama.

## Perubahan API

- Respons detail kuis guru dan payload SSE `done` memuat `coverage_report`, serta `source_point` per soal. Kolom baru nullable, jadi kompatibel mundur. Request pembuatan kuis tidak berubah.
- Status SSE: progres menghitung slot selesai atau gagal; pesan akhir menyebut jumlah gagal.
- Sinkronkan Postman lewat `/api-contract-sync` setelah implementasi.

## Perubahan AI

- Modul baru atau berubah di `ai-services/quizzer/`: `segment` (ditulis ulang), `points` (ekstraksi), `mapping` (pemetaan dan validasi), `prompts` (prompt ekstraksi, pemetaan, audit), `generate` (masukan poin), `validate` (tambah audit), `quizzer_pipeline` (`compute_for_quiz` untuk semua bab, laporan), `context` dihapus (diganti poin). Klien embedding dipindah dari `clarifier/llm_ext` ke `common/embedding.py` (batch dikirim paralel); Quizzer tidak lagi memakainya.
- Konstanta di `quizzer/config.py`: `SEGMENT_TARGET_CHARS`, `SEGMENT_MAX_CHARS`, `OVERLAP_BLOCKS`, `SOURCE_MARGIN_BLOCKS`, `OPTION_LENGTH_RATIO`, `QUIZ_PROMPT_VERSION` (kunci cache Quizzer terpisah, supaya `PROMPT_VERSION` Annoter tidak ikut berubah).
- Model: ekstraksi dan pemetaan `gpt-5.4-mini` effort `low`; generate seperti sekarang; audit dan jawab buta `grok-4.3`. Validator tetap lintas keluarga.
- Estimasi panggilan untuk 40 soal dari 2 bab: ekstraksi sekitar 26 (di-cache pada kuis berikutnya), pemetaan 1, generate 40 ditambah sedikit perbaikan format, jawab buta dan audit Grok sekitar 80. Biaya dan waktu diukur saat verifikasi dan dicatat di `docs/planning/findings.md`; tidak diperkirakan di sini.

## Aksesibilitas

Soal, stimulus, opsi, langkah, dan kesimpulan hanya teks tanpa rujukan visual dan tanpa huruf opsi (urutan opsi diacak). Aturan kejernihan stem tetap ada karena riset melaporkan soal berbasis workflow cenderung kurang jernih. Audit menandai stem ambigu. Setelah implementasi, jalankan agen `a11y-reviewer` pada sampel soal.

## Verifikasi

Pada dua bab sampel (`ai-services/clarifier/eval/blocks/bab1.json`, `bab2.json`) dan lewat API plus worker:

1. Pengukuran cakupan ekstraksi: satu bab utuh dalam satu panggilan vs per segmen; bandingkan jumlah poin dan poin kunci yang terlewat (dipakai menetapkan ukuran segmen).
2. Segmentasi: bab sampel, bab yang headingnya dibuang, dan bab tanpa heading sama sekali; tidak ada job gagal, tidak ada blok terpotong, heading tidak terpisah dari blok setelahnya.
3. Kuota: permintaan 12 soal (6 HOTS dan 6 LOTS) pada dua bab menghasilkan jumlah persis per bab dan level, sebaran segmen merata, kunci A-D seimbang per bab.
4. Verifier: sisipkan soal dengan kunci benar tetapi langkah salah, dan soal dengan dua opsi benar; audit harus menandai keduanya. Dua soal bermasalah yang sudah dikenal dari sampel lama harus tetap tertangkap.
5. Isolasi kegagalan: paksa error pada satu slot; job `done` dengan laporan berisi slot gagal itu.
6. Panjang opsi: kunci = opsi terpanjang pada sampel baru berada di sekitar 25-30% dari soal.
7. Bloom exact-match tiga ulangan (juri grok-4.3 dan Llama; DeepSeek tidak tersedia, F-031) tidak lebih rendah dari baseline 0,71-0,79 di luar derau.
8. Waktu total dan biaya untuk 40 soal dengan `LLM_MAX_WORKERS` 4 dan 8; pilih nilai berdasarkan hasil.
9. Uji otomatis untuk fungsi murni (segmentasi, alokator kuota, validator pemetaan, pemeriksaan panjang opsi, pengacakan) kini berupa tes pytest di `ai-services/tests/quizzer/` (F-027 selesai).
