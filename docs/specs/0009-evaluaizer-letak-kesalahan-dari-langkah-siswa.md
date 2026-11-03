# 0009. Evaluaizer: letak kesalahan dari langkah siswa

- Status: disetujui
- Tanggal: 2026-11-03
- ADR terkait: [0013](../adr/0013-evaluaizer-hanya-letak-kesalahan.md) (menggantikan [0009](../adr/0009-evaluaizer-justifikasi-berpoin.md)). Dasar: [spec 0004](0004-evaluaizer-justifikasi-berpoin.md), [spec 0001](0001-pipeline-quizzer-plan-then-generate.md)

## Masalah

Evaluaizer menghasilkan penjelasan berpoin untuk jawaban salah, termasuk saat siswa tidak menulis langkah. Itu terlalu banyak untuk tujuan sebenarnya: menunjukkan di langkah mana siswa mulai keliru, supaya guru dan siswa melihat letak kesulitannya. Justifikasi yang benar sudah dihasilkan Quizzer (`langkah` dan `kesimpulan`), jadi AI tidak perlu menulis ulang penyelesaian. Uji skenario 2026-11-03 (F-070) juga menunjukkan keluaran yang tidak stabil untuk langkah berisi nilai saja dan penjelasan yang menyalahkan cara siswa yang sah.

## Perilaku yang diharapkan

1. Hasil kuis siswa selalu menampilkan opsi benar, `langkah_kunci`, dan `kesimpulan` dari Quizzer, tanpa AI.
2. AI Evaluaizer hanya berjalan untuk jawaban **salah** yang punya **langkah tertulis dari siswa (scriber)**. Jawaban benar, jawaban salah tanpa langkah, dan langkah kosong atau hanya spasi tidak memanggil AI.
3. Satu panggilan AI membandingkan langkah siswa dengan langkah kunci dan menghasilkan `letak_kesalahan`:
   - `dapat_ditentukan`: false bila langkah tidak memuat proses yang bisa dinilai (nilai saja, deretan bilangan tanpa operasi, tebakan, atau tak bisa dicocokkan dengan soal). Bila false, `langkah_ke` dan `kutipan` kosong.
   - `langkah_ke`: nomor langkah siswa (dari 1) yang pertama kali isinya salah; kosong bila semua langkah siswa benar dan kesalahan terjadi pada pemilihan opsi.
   - `kutipan`: isi langkah itu persis dari siswa (boleh dipotong ke bagian yang salah); kosong bila `langkah_ke` kosong.
   - `keterangan`: satu atau dua kalimat netral tentang apa yang ditulis siswa dan apa yang seharusnya menurut langkah kunci. Tanpa sebab, tanpa saran, tanpa kata "kamu".
4. Cara penyelesaian siswa yang berbeda dari kunci tetapi sah dinilai pada caranya sendiri. Melompati langkah karena hitung mental bukan kesalahan selama isinya benar.
5. Pemeriksa kode menolak keluaran yang strukturnya salah, yang `kutipan`-nya tidak ditemukan pada langkah yang ditunjuk, dan `keterangan` yang memuat markdown, simbol atau rumus mentah, huruf bukan Latin, tanda tanya atau seru, kata ganda berurutan, atau istilah internal. Satu putaran perbaikan otomatis; sisa temuan menandai `perlu_ditinjau`.
6. `error_type`, poin penjelasan berpoin, rekomendasi, dan akar masalah tidak ada lagi di keluaran maupun UI.

## Di luar cakupan

- Rekomendasi atau saran untuk guru, akar masalah, dan agregat kesulitan per kelas.
- Analisis jawaban benar (termasuk mendeteksi menebak).
- Evaluasi ulang hasil lama setelah soal berubah (soal terkunci saat publish).
- Antarmuka (frontend belum dimulai).

## Perubahan data

Migrasi menambah dua kolom nullable di `soal_jawaban`: `letak_kutipan` (Text) dan `letak_dapat_ditentukan` (Boolean). `divergence_step` dipakai sebagai `langkah_ke` dan `diagnosis` sebagai `keterangan`. Kolom `error_type`, `justification_points`, dan `personalized_justification` tidak lagi diisi dan tetap ada (belum dihapus; penghapusan menyusul di migrasi terpisah). Baris lama yang sudah dievaluasi tetap dianggap sudah dievaluasi dan tampil tanpa letak kesalahan.

## Perubahan API

`GET /api/evaluaizer/student/quizzes/{id}/results`: item hasil kehilangan `justification` dan mendapat `letak_kesalahan` (`dapat_ditentukan`, `langkah_ke`, `kutipan`, `keterangan`, `perlu_ditinjau`) atau null bila tidak ada analisis (jawaban benar, tanpa langkah, atau belum dievaluasi). `evaluasi_diproses` dan `evaluasi_gagal` tetap. `langkah_kunci`, `kesimpulan`, `correct_option`, dan `langkah` siswa tidak berubah. Sinkron ke Postman setelah implementasi.

## Perubahan AI

Prompt, skema keluaran, dan pemeriksa `evaluaizer` ditulis ulang; satu panggilan per jawaban salah ber-langkah (`gpt-5.4-mini`, effort low). Biaya turun karena jawaban tanpa langkah tidak lagi memanggil model dan keluarannya jauh lebih pendek.

## Aksesibilitas

`keterangan` dibacakan pembaca layar: tanpa markdown, notasi dengan kata, tanda negatif disebut, opsi disebut bersama isinya. `kutipan` adalah teks siswa apa adanya (sudah tampil di `langkah`).

## Verifikasi

- Tes murni untuk pemeriksa, alur evaluasi (coba ulang, tanpa langkah tidak memanggil model), dan backend (`needs_evaluation`, penyimpanan, hasil).
- Evaluasi 3 ulangan atas kasus di `evaluaizer/eval/cases.json` (15 kasus lama dikonversi, satu kasus tanpa langkah dibuang, dan 11 skenario baru dari F-070) dengan kebenaran dasar: letak langkah, `dapat_ditentukan`, dan `kutipan` yang berdasar. Tanpa model juri. Hanya atas perintah user.
- `uv run pytest -q` dari root hijau.

## Batas yang diterima

Evaluasi 26 kasus x 3 ulangan (empat putaran, `gpt-5.4-mini` effort low; satu putaran effort medium): letak langkah tepat sekitar 96 sampai 99 persen per putaran, `dapat_ditentukan` hampir selalu tepat, dan pemeriksa kode bersih. Sisa kegagalan, terutama `skenario_loncat_mental_lalu_salah` (meleset sekitar 1 dari 3 ulangan, menunjuk langkah sesudahnya atau menyatakan semua langkah sesuai), berupa kesalahan perbandingan model yang tidak bisa ditandai pemeriksa karena hasilnya sah secara struktur. Keputusan user (2026-11-03): diterima; guru meninjau hasil dan letak yang meleset satu langkah tetap membantu. Effort medium tidak memberi perbaikan yang jelas (77/78 vs 76/78) sehingga effort tetap low.
