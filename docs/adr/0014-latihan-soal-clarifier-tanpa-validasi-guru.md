# 0014. Latihan soal buatan AI di Clarifier tanpa validasi guru

- Status: diterima
- Tanggal: 2026-11-03

## Konteks

Aturan inti proyek: keluaran AI divalidasi guru sebelum sampai ke siswa. Soal kuis Quizzer mengikutinya (guru meninjau, mengedit, lalu mempublikasikan). Untuk Clarifier sebagai teman belajar, user memutuskan siswa boleh meminta soal latihan yang disintesis AI dari modul dan tool, tanpa peninjauan guru. Uji Quizzer menunjukkan soal buatan AI masih bisa salah (kunci meleset atau tanpa opsi benar pada sebagian kecil soal, ditangkap audit dan guru).

## Keputusan

- Latihan buatan AI di Clarifier dikecualikan dari aturan validasi guru; risikonya diterima user.
- Pengaman: soal dibuat dengan komponen pembuatan dan verifikasi yang sama dengan Quizzer (pemeriksa kode, jawab buta, audit) dan hanya dikirim bila lolos tanpa temuan berat; bila gagal, buat ulang sekali, lalu katakan jujur belum bisa.
- Soal berlabel latihan AI yang belum ditinjau guru, tidak masuk nilai, tidak ditulis ke `soal_jawaban`, dan tidak dianalisis Evaluaizer.
- Cakupan awal: soal tanpa stimulus atau dengan stimulus teks; stimulus bergambar menyusul setelah ada pemeriksa geometri.
- Pengecualian hanya berlaku untuk latihan di Clarifier. Soal kuis, anotasi modul, dan jawaban tanya jawab biasa tetap mengikuti aturan yang ada.

## Konsekuensi

- Siswa tunanetra bisa menerima soal dengan kunci salah dalam sebagian kecil kasus tanpa guru menyaring. Mitigasi hanya pemeriksaan otomatis dan label.
- Komponen Quizzer tidak dipindah ke `common/`: backend merangkai `clarifier.practice` (pilih sumber) dan `quizzer_pipeline.generate_practice` (buat dan verifikasi), sehingga fitur tetap tidak saling mengimpor (ADR 0004).
- Pengaman diperketat dibanding kuis guru: tanpa temuan sama sekali (bukan hanya temuan berat), satu perbaikan, selain itu ditolak; stimulus bertipe ditolak; level C1 sampai C3.
- Perlu ukuran mutu terpisah (tingkat soal lolos dan salah kunci) sebelum fitur ini dibuka ke siswa.
