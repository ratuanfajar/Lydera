# 0004. Evaluaizer: justifikasi berpoin dari letak kesalahan

- Status: selesai
- Tanggal: 2026-10-28
- ADR terkait: -

## Masalah

Setelah kuis selesai, siswa tunanetra yang menjawab salah menerima satu paragraf justifikasi (`personalized_justification`). Pembaca layar membacakannya sebagai satu blok panjang, siswa tidak bisa melompat ke bagian yang dibutuhkan, dan isinya tidak selalu berguna:

- tidak melanjutkan dari langkah yang salah sampai kesimpulan kunci, bahkan tidak menyebut jawaban akhir yang benar (F-007);
- untuk jawaban salah tanpa langkah siswa, hasilnya berisi kalimat meta seperti "catatan langkah siswa tidak disertakan" (F-006, F-015);
- soal HOTS dievaluasi tanpa stimulusnya, padahal data soal ada di stimulus;
- satu panggilan LLM yang gagal menggagalkan seluruh respons hasil kuis.

## Perilaku yang diharapkan

Untuk setiap jawaban yang salah, siswa menerima justifikasi berupa poin bernomor yang bisa ditelusuri satu per satu:

1. **Poin awal:** meringkas bagian langkah siswa yang sudah benar sebelum kesalahan (dilewati bila siswa salah sejak langkah pertama atau tidak menulis langkah).
2. **Poin letak kesalahan:** menyebut langkah siswa yang pertama menyimpang dan sebab kesalahannya, dengan ramah.
3. **Poin perbaikan:** melanjutkan dari titik yang salah, langkah demi langkah, sampai kesimpulan kunci.
4. **Poin terakhir** menyebut jawaban akhir yang benar.

Aturan:

- Tiap poin satu sampai dua kalimat, tanpa markdown, tanpa simbol mentah (notasi ditulis dengan kata), tanpa kalimat pembuka dan tanpa kalimat meta tentang langkah yang hilang.
- Tiap poin memuat `step_ref`: nomor langkah kunci guru yang dibahas poin itu, atau `null` bila poin tidak terkait satu langkah kunci; dan `is_divergence`: `true` pada satu poin yang menyebut letak kesalahan (bila ada letaknya), agar klien dapat membacakan "letak kesalahan" sebelum poin itu.
- Kata "langkah pertama, kedua, ..." di teks hanya untuk langkah siswa dan sama dengan `divergence_step`; langkah kunci disebut isinya, bukan nomornya. Teks tidak memakai istilah internal ("langkah kunci", "materi sumber"), memakai "kamu", menulis variabel dan persamaan dengan kata, menyebut tanda "negatif" dan pengelompokan hasil kali, dan menyebut isi opsi bersama hurufnya. `diagnosis` satu kalimat inti tanpa angka.
- `divergence_step` tetap nomor langkah siswa (mulai dari 1) tempat penyimpangan pertama, atau `null` bila siswa salah paham sejak awal, langkahnya tidak bisa dicocokkan, atau tidak menulis langkah.
- `error_type`: salah satu dari `salah_konsep`, `salah_prosedur`, `salah_hitung`, `salah_baca_soal`, `tanpa_langkah`, `lainnya`.
- Jawaban salah tanpa langkah siswa tetap dievaluasi LLM (putusan F-006): poin menjelaskan mengapa opsi yang dipilih keliru, lalu langkah penyelesaian yang benar sampai kesimpulan; `divergence_step` `null`, `error_type` `tanpa_langkah`.
- Jawaban benar tidak memanggil LLM.
- Hasil kuis memuat `langkah_kunci` (langkah penyelesaian guru) untuk semua soal supaya `step_ref` dapat dirujuk dan siswa yang benar dapat membaca pembahasan.
- Evaluasi memakai stimulus soal (bila ada) selain materi sumber, pertanyaan, opsi, langkah kunci, kesimpulan, dan langkah siswa. Isi langkah siswa diperlakukan sebagai data, bukan instruksi.
- Keluaran LLM diperiksa kode (struktur, jumlah poin, `step_ref` dan `divergence_step` dalam jangkauan, tepat satu `is_divergence` bila ada letak kesalahan, simbol mentah, pola angka-huruf seperti `3x`, huruf bukan Latin, markdown, kalimat meta dan istilah internal). Bila ada masalah, satu kali perbaikan otomatis; bila masih ada masalah, hasil yang lebih baik tetap disimpan dan `perlu_ditinjau` bernilai benar. Bila perbaikan itu sendiri gagal, hasil pertama dipakai. Hasil tanpa poin yang dapat dipakai dihitung sebagai kegagalan (`evaluasi_gagal`). Nomor langkah di luar jangkauan dikosongkan sebelum disimpan.
- Panggilan LLM dibatasi `LLM_MAX_WORKERS` bersamaan; transaksi DB dilepas sebelum menunggu LLM; langkah siswa dibersihkan dari `<`, `>`, dan baris baru, dibatasi 30 langkah dan 1000 karakter per langkah.
- Kegagalan evaluasi satu soal tidak menggagalkan hasil kuis: soal itu dikembalikan tanpa justifikasi (`justification` `null`, `evaluasi_gagal` benar) dan dicoba lagi pada permintaan berikutnya; soal lain tetap disimpan.
- Hasil yang tersimpan lama (satu paragraf, tanpa poin) dievaluasi ulang secara lazy pada permintaan berikutnya, satu kali. Selama belum dievaluasi ulang (diproses atau gagal), `justification` bernilai `null`; paragraf lama tidak ditampilkan karena tidak melewati pemeriksa kode.
- Jawaban yang gagal dievaluasi tidak dicoba lagi selama jeda singkat (45 detik untuk kegagalan sementara, 300 detik untuk keluaran yang tidak valid atau ditolak filter); selama jeda `evaluasi_gagal` bernilai benar.
- Evaluasi diantrekan ke taskiq (`evaluate_quiz_answers_task`) begitu penilaian kuis selesai, sehingga biasanya sudah ada ketika siswa membuka hasil. Permintaan hasil tetap mengevaluasi sendiri yang belum ada sebagai cadangan.
- Evaluasi satu siswa pada satu kuis hanya berjalan di satu proses (kunci Redis, tidak menunggu). Permintaan hasil yang bertemu kunci terpakai mengembalikan jawaban yang belum dievaluasi dengan `justification` `null` dan `evaluasi_diproses` benar; klien mengulang permintaan beberapa detik kemudian.

## Di luar cakupan

- Validasi guru atas justifikasi per siswa. Justifikasi dibuat setelah siswa menjawab sehingga tidak bisa divalidasi sebelumnya; mitigasinya pemeriksaan kode dan landasan pada langkah kunci yang sudah disetujui guru. Tampilan ke guru (dasbor kesalahan umum) belum ada.
- UI Flutter.
- Hasil yang mengendalikan mastery atau nilai.
- Mengubah cara penilaian jawaban (benar atau salah) atau pembuatan langkah kunci.

## Perubahan data

Migrasi (satu revisi) pada `soal_jawaban`:

- `error_type` Text nullable.
- `justification_points` JSONB nullable (daftar `{point, step_ref}`), `none_as_null`.
- `needs_review` Boolean not null, default false.

`personalized_justification` tetap diisi (poin digabung menjadi satu teks dengan awalan "Poin satu.", "Poin dua.", dan seterusnya, ditulis dengan kata supaya angka urut tidak terbaca sebagai bagian rumus) supaya konsumen lama tidak rusak. Tidak ada migrasi data; baris lama dikenali dari `justification_points` kosong.

## Perubahan API

`GET /evaluaizer/student/quizzes/{quiz_request_id}/results` (peran siswa), item hasil:

- tambah `langkah_kunci: list[str]`;
- `justification` (null bila jawaban benar atau evaluasi gagal) berisi `divergence_step`, `error_type`, `diagnosis`, `points: [{point, step_ref, is_divergence}]`, `personalized_justification`, `perlu_ditinjau`;
- tambah `evaluasi_gagal: bool`;
- tambah `evaluasi_diproses: bool` (benar bila jawaban salah itu sedang dievaluasi proses lain; klien mengulang permintaan).

Tidak ada endpoint baru. Koleksi Postman disinkronkan lewat `api-contract-sync`.

## Perubahan AI

- Prompt Evaluaizer memakai format seragam (`common/prompt_format`), keluaran JSON: `divergence_step`, `error_type`, `diagnosis`, `justification_points`. Satu panggilan per jawaban salah.
- Model `gpt-5.4-mini`, effort ditetapkan lewat evaluasi (`EVALUAIZER_EFFORT`).
- `ai-services/evaluaizer/checks.py`: pemeriksaan kode; satu kali perbaikan.
- Evaluasi di `ai-services/evaluaizer/eval/`: kasus dengan kebenaran dasar `divergence_step`, 3 ulangan.
- Tidak ada cache LLM (hasil disimpan di DB).

## Aksesibilitas

- Poin pendek bernomor memudahkan pembaca layar melompat dan mengulang satu poin.
- Teks tanpa markdown dan simbol mentah; notasi diverbalisasi.
- Nada ramah, tidak menghakimi siswa.

## Verifikasi

- Evaluasi `eval/run_eval.py` pada kasus: salah di langkah awal, tengah, akhir, tanpa langkah, salah konsep, salah baca opsi, langkah berisi simbol, langkah berisi upaya injeksi prompt; 3 ulangan. Ukuran: `divergence_step` sesuai, struktur lolos pemeriksaan kode, poin terakhir menyatakan kesimpulan kunci (juri LLM lintas keluarga, diperiksa manual), tanpa kalimat meta.
- Uji unit pemeriksa kode dan penggabungan poin.
- Migrasi di database dev, lalu alur nyata: siswa menjawab salah dengan dan tanpa langkah, selesai, ambil hasil; ambil ulang tanpa panggilan LLM; baris lama dievaluasi ulang satu kali; kegagalan satu soal disimulasikan.
- Sinkronisasi Postman.
