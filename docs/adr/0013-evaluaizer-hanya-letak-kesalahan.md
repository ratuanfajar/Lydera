# 0013. Evaluaizer hanya menunjuk letak kesalahan

- Status: diterima
- Tanggal: 2026-11-03
- Menggantikan: [0009](0009-evaluaizer-justifikasi-berpoin.md)

## Konteks

ADR 0009 membuat Evaluaizer menulis penjelasan berpoin lengkap untuk setiap jawaban salah, termasuk saat siswa tidak menulis langkah. Justifikasi yang benar sudah dihasilkan Quizzer dan tersimpan (`langkah`, `kesimpulan`). Uji skenario 2026-11-03 (12 kasus x 3 ulangan, F-070) menunjukkan: langkah berisi nilai saja memberi jenis kesalahan dan letak yang berubah-ubah; cara siswa yang sah dengan tanda keliru dijelaskan lewat cara kunci sehingga tampak salah; dua bacaan memuat tanda tanya atau kata ganda yang lolos pemeriksa.

## Keputusan

- Justifikasi jawaban (`langkah_kunci`, `kesimpulan`) diambil dari Quizzer, tanpa AI.
- AI Evaluaizer hanya berjalan untuk jawaban salah yang punya langkah tertulis siswa, dan hanya menunjuk letak kesalahan dengan membandingkan langkah siswa terhadap langkah kunci: `dapat_ditentukan`, `langkah_ke`, `kutipan`, `keterangan`.
- Langkah yang tidak memuat proses dinyatakan `dapat_ditentukan = false` alih-alih ditebak.
- Cara siswa yang sah dinilai pada caranya sendiri; melompati langkah karena hitung mental bukan kesalahan.
- Tidak ada `error_type`, poin penjelasan, rekomendasi, atau akar masalah. Jawaban benar tidak dianalisis.
- Pemeriksa kode memastikan `kutipan` benar-benar ada pada langkah yang ditunjuk dan menolak tanda tanya, tanda seru, kata ganda, simbol mentah, dan istilah internal.

## Konsekuensi

- Lebih murah dan lebih mudah diukur: kebenaran dasar cukup nomor langkah dan status `dapat_ditentukan`, tanpa model juri.
- Siswa tanpa scriber tidak mendapat keterangan AI; UI hanya menampilkan opsi benar dan justifikasi Quizzer.
- Putusan F-006 (jawaban salah tanpa langkah tetap dievaluasi) dicabut.
- Kontrak hasil kuis berubah (`justification` diganti `letak_kesalahan`); frontend belum ada sehingga belum ada konsumen yang rusak.
- Kolom lama (`error_type`, `justification_points`, `personalized_justification`) tidak lagi diisi dan dihapus di migrasi terpisah.
