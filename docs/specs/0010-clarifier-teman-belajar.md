# 0010. Clarifier sebagai teman belajar siswa tunanetra

- Status: selesai (tahap 1, 2, 3, 5 terimplementasi dan diuji dengan tes murni; tahap 4 dibatalkan; belum diukur dengan LLM)
- Tanggal: 2026-11-03
- ADR terkait: [0014](../adr/0014-latihan-soal-clarifier-tanpa-validasi-guru.md). Dasar: [spec 0005](0005-clarifier-pencarian-hibrida-dan-sumber-oer.md), [spec 0006](0006-clarifier-rumus-tampil-dan-bacaan.md), [ADR 0010](../adr/0010-clarifier-pencarian-hibrida-dan-sumber-oer.md), [ADR 0011](../adr/0011-clarifier-bacaan-dari-latex.md), [ADR 0008](../adr/0008-tabel-dua-mode-baca.md)

## Masalah

Clarifier sekarang menjawab pertanyaan satu per satu dari modul dan sumber luar terbatas, dengan sitasi terverifikasi dan bacaan rumus dari verbalizer. Siswa tunanetra belum bisa memakainya sebagai teman belajar: jawaban tidak menampilkan tabel, sumber tabel atau gambar tidak ikut, tidak bisa meminta soal latihan, dan Clarifier masih bisa dipakai saat kuis berlangsung.

## Keputusan user (2026-11-03)

- Tidak memakai STT dan TTS: siswa memakai TalkBack dan keyboard.
- Respons Clarifier tetap seperti biasa (satu jawaban); tanpa jawaban berlapis, perintah kendali, memori belajar, atau preferensi.
- Clarifier tidak boleh dipakai saat kuis berlangsung.
- Guru tidak melihat topik yang ditanyakan siswa.
- Siswa boleh meminta soal latihan; AI mensintesisnya dari modul dan tool yang tersedia, risikonya diterima (ADR 0014).
- Jawaban boleh berisi rumus (LaTeX dengan narasi berdampingan, seperti Annoter dan Quizzer), tabel, dan gambar; kemampuan dibagi dengan Annoter dan Quizzer lewat `common/`. Dikerjakan bertahap.

## Tahapan

Tiap tahap diuji dengan tes murni, dilaporkan, lalu disinkronkan ke Postman sebelum tahap berikutnya. Evaluasi yang memanggil Azure hanya atas perintah user.

### Tahap 1: kunci saat kuis dan rumus berpasangan
1. `POST /clarifier/student/sessions/{id}/messages` ditolak 400 bila siswa punya sesi kuis aktif di kelas sesi itu (progres sudah dimulai, belum selesai, dan belum melewati batas waktu pengerjaan atau batas akhir kuis). Membuat dan melihat sesi tetap boleh.
2. Respons jawaban memuat `rumus`: daftar `{latex, bacaan}` untuk tiap rumus unik di `summary` (urut kemunculan), selain `message` dan `message_markup` yang sudah ada. Narasi tiap rumus dari verbalizer bersama yang sama.

### Tahap 2: tabel terstruktur
Model boleh menyertakan `tabel` (`judul`, `kolom`, `baris`) di `compose_answer` hanya bila sumber memuat data tabular atau jawabannya perbandingan beberapa nilai. Kode memvalidasi (struktur, ukuran, tanpa simbol mentah, angka berasal dari sumber) dan menurunkan teks bacaan (ringkasan dan telusur) lewat modul tabel bersama di `common/` yang dipakai juga oleh stimulus Quizzer. Respons memuat `tabel` dan bacaannya.

### Tahap 3: blok sumber (tabel dan gambar asli)
Sumber `modul` pada jawaban memuat blok aslinya bila tabel atau gambar: tipe blok, `tabel` terstruktur, berkas gambar, dan deskripsi Annoter sebagai narasi. Klien menampilkan blok itu di samping jawaban. Model tidak menghasilkan gambar. Gambar buatan model (SVG) ditunda sampai ada pemeriksa geometri.

### Tahap 4: dibatalkan
Penjelasan soal dari hasil kuis dibatalkan (keputusan user 2026-11-03): Clarifier berdiri sendiri dan tidak membahas kuis. Kodenya (endpoint `/explain`, konteks soal, sumber `soal`) sudah dibuang. Kunci Clarifier saat kuis berlangsung (tahap 1) tetap berlaku.

### Tahap 5: latihan soal buatan AI di antarmuka chat
Clarifier adalah satu chatbot asisten belajar; latihan soal hanya di percakapan, bukan halaman atau endpoint baru. Siswa menulis permintaan di chat (misalnya buatkan soal latihan tentang garis singgung lingkaran), model memanggil tool `request_practice` (tanpa menulis soal sendiri), dan backend membuat soalnya dengan `quizzer_pipeline.generate_practice` dari bagian modul relevan (penilai retrieval yang sama dengan jawaban). Pengaman ADR 0014: hanya dikirim bila pemeriksa kode, jawab buta, dan audit tidak menemukan apa pun (satu perbaikan, selain itu ditolak jujur); berlabel latihan AI belum ditinjau guru; tidak masuk nilai atau Evaluaizer.

Rincian yang dibangun, semuanya lewat `POST /clarifier/sessions/{id}/messages`:
- Soal tampil sebagai pesan asisten biasa (`message` bacaan, `message_markup` bila berrumus) berisi label, tingkat, stimulus teks bila ada, soal, pilihan A sampai D, dan petunjuk mengetik huruf. Respons membawa `latihan` `{tahap: "soal", pilihan}`; tahap `ditolak` bila topik tak ada di modul, pencarian gagal, atau soal tidak lolos.
- Soal dan kunci disimpan di Redis (2 jam), satu latihan aktif per sesi (latihan baru menggantikan); tidak ada tulis ke tabel soal.
- Pesan siswa yang hanya berisi satu huruf pilihan (A sampai D, boleh diawali jawaban atau opsi) saat ada latihan aktif dibaca sebagai jawaban: dibalas pesan hasil (`latihan` `{tahap: "hasil", benar}`) berisi kunci, langkah, kesimpulan, dan label; latihan dihapus. Pesan lain tetap pertanyaan biasa dan latihan tetap aktif.
- Kunci kuis aktif (tahap 1) berlaku. Batas 10 permintaan latihan per siswa per jam (429).

## Di luar cakupan

STT dan TTS, jawaban berlapis dan perintah kendali, memori atau personalisasi, tampilan topik untuk guru, preferensi, gambar buatan model, dan antarmuka (frontend belum dimulai).

## Perubahan data dan API

Tahap 1 tanpa migrasi; `ChatAnswerResponse` mendapat `rumus` dan pesan baru 400. Tahap berikutnya menambah field respons (`tabel`, blok sumber) dan, bila perlu, kolom JSONB di `chat_messages`; tiap tahap menulis perubahannya sendiri dan menyinkronkan Postman.

## Aksesibilitas

Semua teks bacaan tanpa markdown dan tanpa simbol mentah; rumus dan tabel selalu disertai narasi yang diturunkan modul bersama. Tabel dan gambar sumber tampil dengan deskripsi Annoter yang sudah ditinjau guru.

## Verifikasi

Tes murni per tahap (`uv run pytest -q` hijau), lalu uji asap dengan data dev atas perintah user.
