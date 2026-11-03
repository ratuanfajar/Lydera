# 0009. Evaluaizer: justifikasi berpoin dengan pemeriksa kode

- Status: digantikan oleh [0013](0013-evaluaizer-hanya-letak-kesalahan.md) (2026-11-03)
- Tanggal: 2026-10

## Konteks

Justifikasi untuk jawaban salah berupa satu paragraf: tidak melanjutkan dari langkah yang salah sampai kesimpulan, tidak menyebut jawaban akhir, memuat kalimat meta bila siswa tidak menulis langkah, mengabaikan stimulus soal, dan satu panggilan LLM yang gagal menggagalkan seluruh hasil kuis. Spec: [0004](../specs/0004-evaluaizer-justifikasi-berpoin.md).

## Keputusan

- Satu panggilan LLM per jawaban salah menghasilkan `divergence_step`, `error_type`, `diagnosis`, dan `justification_points` bernomor (`point`, `step_ref` ke langkah kunci). Urutan poin: ringkasan langkah benar, letak dan sebab kesalahan, perbaikan sampai kesimpulan kunci, jawaban akhir.
- Prompt memakai format seragam, satu contoh few-shot, dan membungkus catatan siswa sebagai data. Stimulus soal ikut dikirim.
- Pemeriksa kode (`evaluaizer/checks.py`) memeriksa struktur, jangkauan nomor langkah, tepat satu poin `is_divergence`, simbol mentah, pola angka-huruf (`3x`), huruf bukan Latin, markdown, kalimat meta, dan istilah internal; satu perbaikan otomatis; hasil yang lebih baik disimpan dan `needs_review` menandai yang masih bermasalah. Hasil tanpa poin dihitung gagal.
- Prompt melarang istilah internal, mewajibkan "kamu", variabel dan persamaan dengan kata, tanda "negatif", pengelompokan hasil kali, isi opsi bersama hurufnya, dan nomor "langkah ke-n" hanya untuk langkah siswa. Diperbaiki setelah tinjauan aksesibilitas: urutan operasi tanpa pengelompokan dan tanda negatif yang hilang lolos dari juri pada satu ulangan putaran 2.
- Siswa tanpa langkah tetap dievaluasi (putusan F-006), tanpa kalimat meta. Jawaban benar tidak memanggil LLM.
- Backend: DB hanya dipakai berurutan dan panggilan LLM paralel di thread; kegagalan satu soal tidak menggagalkan hasil (`evaluasi_gagal`, dicoba lagi setelah jeda singkat); baris lama tanpa poin dievaluasi ulang sekali (lazy) dan selama belum selesai `justification` bernilai `null` (paragraf lama tidak ditampilkan karena tidak melewati pemeriksa kode); respons memuat `langkah_kunci` dan `kesimpulan` setelah kuis selesai.
- Data: `soal_jawaban.error_type`, `justification_points` (JSONB), `needs_review`; `personalized_justification` tetap diisi.

## Hasil evaluasi (10 kasus, 3 ulangan, `gpt-5.4-mini` effort low, juri `grok-4.3`)

| Ukuran | Putaran 1 | Putaran 2 (prompt diagnosis diperbaiki) | Putaran 4 (setelah tinjauan aksesibilitas) |
|---|---|---|---|
| `divergence_step` sesuai kebenaran dasar | 30/30 | 30/30 | 29/30 (kasus median: langkah 1 dinilai salah, yang diterima 2) |
| `error_type` termasuk yang diterima | 30/30 | 30/30 | 30/30 |
| Lolos pemeriksa kode (aturan makin ketat) | 30/30 | 30/30 | 30/30 (putaran 3 dengan aturan mata uang terlalu ketat: 26/30, dilonggarkan) |
| Juri: jawaban akhir benar dinyatakan | 30/30 | 30/30 | 30/30 |
| Juri: matematika akurat | 30/30 | 30/30 | 30/30 |
| Juri: perbaikan berlanjut dari letak kesalahan | 28/30 | 27/30 | 28/30 (yang gagal semua pada kasus tanpa langkah, tidak ada letak kesalahan untuk dilanjutkan) |
| Juri menemukan kalimat catatan hilang | 0/30 | 0/30 | 0/30 |

Kasus mencakup salah di langkah awal, tengah, dan akhir, salah konsep, siswa tanpa langkah, soal dengan stimulus, langkah benar tetapi opsi salah dipilih, langkah bersimbol, dan upaya injeksi prompt di langkah siswa (diabaikan; kesalahan nyata tetap dijelaskan).

Batas hasil: kasus dibuat penulis dengan soal sederhana, sebagian aturan dan contoh disusun setelah melihat putaran pertama, jadi angka memihak; juri adalah LLM; belum diuji pada langkah tulisan siswa nyata (salah ketik, dikte, bahasa campuran) dan belum ada uji dengar. Evaluasi berjalan saat siswa membuka hasil sehingga tidak bisa divalidasi guru lebih dulu; mitigasinya pemeriksaan kode dan landasan pada langkah kunci yang sudah disetujui guru.

## Konsekuensi

- Pemeriksaan kode tidak menangkap kesalahan makna seperti tanda matematika yang keliru; itu hanya terlihat oleh juri dan pemeriksaan manual.
- Evaluasi dijalankan satu kali per siswa dan kuis oleh `AnswerEvaluator` di bawah kunci Redis (`evaluaizer_lock:{kuis}:{siswa}`, kedaluwarsa 300 detik, tidak menunggu). Permintaan hasil yang bertemu kunci terpakai mengembalikan jawaban yang belum selesai dengan `evaluasi_diproses` benar dan `justification` `null`; klien mengulang beberapa detik kemudian. Bila proses pemegang kunci mati, kunci kedaluwarsa dan permintaan berikutnya mengevaluasi ulang. Tiap panggilan evaluasi dibatasi 270 detik (termasuk antre) supaya selesai sebelum kunci kedaluwarsa; yang melewatinya dihitung gagal. Jawaban yang gagal diberi penanda Redis (`evaluaizer_failed:{jawaban}`): selama penanda ada, permintaan hasil melaporkan `evaluasi_gagal` tanpa memanggil LLM lagi. Jedanya 45 detik untuk kegagalan sementara (timeout, koneksi, batas laju) dan 300 detik untuk `ValueError` (filter konten, keluaran terpotong, tidak ada poin), sehingga kegagalan permanen tidak membakar biaya di setiap permintaan, sedangkan kegagalan sementara tidak ditahan lama. Penanda dipasang setelah hasil yang berhasil di-commit, dan kegagalan Redis di sana hanya dicatat. Thread LLM yang sudah berjalan tidak bisa dibatalkan; hasilnya dibuang bila terlambat. Redis wajib tersedia untuk endpoint hasil kuis.
- Saat penilaian kuis selesai (`process_exam_review_task`), task `evaluate_quiz_answers_task` diantrekan ke taskiq sehingga evaluasi biasanya sudah ada ketika siswa membuka hasil. Permintaan hasil tetap mengevaluasi sendiri jawaban yang belum dievaluasi (cadangan bila antrean atau worker gagal, atau untuk baris lama). Gagal mengantre hanya dicatat. Uji nyata (4 jawaban salah): 18 detik setelah selesai semua sudah terevaluasi tanpa permintaan hasil, permintaan hasil berikutnya 0,0 detik; dua permintaan bersamaan pada baris belum dievaluasi: satu 0,4 detik dengan `evaluasi_diproses` pada 4 soal, satu 20,9 detik dengan 4 justifikasi.
- Deteksi penilaian macet di permintaan hasil kini memakai `quiz_progress.review_started_at` (migrasi `cb1cb0782cef`, diisi saat penilaian mulai), bukan `started_at` kuis. Sebelumnya hampir semua penilaian yang sedang berjalan dianggap macet dan dinilai ulang inline. Status kuis juga diperbarui (`refresh`) setelah penilaian inline; sebelumnya permintaan itu tetap gagal "belum selesai". Baris `PROCESSING` lama tanpa `review_started_at` dianggap macet.
- Tanpa worker taskiq (atau modul `app.tasks.evaluaizer_tasks` tidak ada di perintah worker), hasil pertama tetap memakan beberapa detik (sekitar 14 sampai 20 detik untuk 4 jawaban salah paralel).
- Opsi pada poin disebut dengan huruf; urutan opsi sudah tetap saat kuis berjalan sehingga aman.
- Klien menampilkan `points` sebagai daftar bernomor; `step_ref` dapat dipakai untuk menautkan ke `langkah_kunci`.
- Alternatif yang ditunda: tampilan guru untuk `error_type` per kelas.

## Putaran 5 dan 6: langkah siswa berantakan

Enam kasus ditambahkan (16 kasus): salah ketik dan singkatan, satu baris yang memuat benar dan salah, narasi yang bercampur angka, dikte dengan koreksi diri, loncat langsung ke jawaban, dan simbol `%`, `x`, `-` mentah di langkah siswa. Kebenaran dasar ditulis sebelum dijalankan.

- Putaran 5 (prompt tanpa perubahan): `divergence_step` 46/48, enam kasus baru 18/18. Dua miss ada pada kasus geometri, yang mencampur langkah benar yang samar dengan langkah salah sesudahnya; teks bahkan menyebut "langkah pertama" untuk isi langkah kedua. Ulangan terpisah kasus itu: 11/12, sehingga total 12/15 sebelum perbaikan.
- Perbaikan: aturan prompt bahwa langkah yang isinya benar bukan penyimpangan, dan poin letak kesalahan menyebut isi langkah itu. Sesudah perbaikan, geometri 15/15 dan putaran 6 `divergence_step` 48/48, `error_type` 48/48, lolos pemeriksa kode 48/48, juri jawaban akhir 48/48, matematika akurat 47/48 (satu temuan juri diperiksa manual dan salah: jumlah negatif lima untuk akar dua dan tiga benar), perbaikan berlanjut dari letak kesalahan 46/48 (kasus tanpa letak kesalahan yang jelas). Aturan itu ditulis setelah melihat kegagalan, jadi angka putaran 6 memihak untuk kasus geometri.
- Satu hasil kasus loncat langsung menandai poin ringkasan soal sebagai letak kesalahan; teksnya benar tetapi kurang tepat sasaran. Belum diperbaiki.
