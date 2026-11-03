# 0015. Chunk Clarifier berbasis ukuran, heading hanya titik potong

- Status: diterima
- Tanggal: 2026-11-03
- Menggantikan: bagian chunk pada [0010](0010-clarifier-pencarian-hibrida-dan-sumber-oer.md)

## Konteks

Chunk lama dibentuk per heading dan hanya dipecah di batas block pada 1.500 karakter. Pada data uji bab 1, 14 dari 84 chunk berukuran di bawah 200 karakter (heading tanpa isi atau section satu kalimat) dan hanya 27 yang di atas 400 karakter, sehingga embedding chunk pendek lemah dan mudah salah peringkat. Quizzer sudah berpindah ke pemecahan menurut blok dan karakter dengan heading sebagai titik potong pilihan karena alasan yang sama.

## Keputusan

- Chunk dikemas dari block berurutan (heading ikut sebagai block): ditutup di heading berikutnya setelah mencapai 600 karakter, atau di batas block sebelum 1.200 karakter.
- Heading tidak ditinggal sendirian di ujung chunk. Chunk terakhir di bawah 250 karakter digabung ke chunk sebelumnya bila muat.
- Block terakhir sebuah chunk (maksimal 300 karakter) diulang di awal chunk berikutnya sebagai overlap, hanya bila chunk itu punya lebih dari satu block.
- Block pertama tiap chunk harus unik dalam satu bab karena dipakai sebagai `reference` sitasi dan untuk mengambil blok tabel dan gambar asli; karena itu block tunggal yang melebihi batas tidak dipecah.
- Heading tetap menjadi awalan teks chunk. `block_ids`, `formula_norm`, dan penyaringan section ISBN dan hak cipta tidak berubah.
- Pustaka pemecah teks (LangChain) tidak dipakai: ia bekerja pada string datar dan menghilangkan pemetaan ke block.

## Konsekuensi

- Semua bab yang sudah terindeks harus diindeks ulang (`POST /api/clarifier/chapters/{id}/reindex` atau `/classrooms/{id}/reindex`).
- Pada data uji bab 1, chunk di bawah 200 karakter turun dari 14 dari 84 menjadi 0 dari 65, dengan median 1.104 karakter; bab 2 dari 7 dari 62 menjadi 0 dari 53.
- Angka 600, 1.200, 250, dan 300 dipilih dari distribusi ukuran, belum dari evaluasi retrieval. Recall@5 pada 17 pertanyaan dan 14 pertanyaan rumus (ADR 0010) harus diukur ulang sebelum angka itu dianggap final.
