# 0001. ai-services adalah komputasi murni

- Status: diterima
- Tanggal: 2026-09-01

## Konteks

Keluaran MLLM tidak deterministik dan bisa salah. Jika modul AI menulis database sendiri, kesalahan masuk ke data siswa tanpa lapisan validasi, dan sulit diuji tanpa database.

## Keputusan

Semua modul di `ai-services/` hanya menerima masukan dan mengembalikan hasil; tidak ada akses DB. Backend membaca data dari DB, memanggil fungsi AI (sinkron, lewat `asyncio.to_thread`), memvalidasi hasil, lalu menyimpannya. Alur: MLLM, JSON tervalidasi, backend, DB.

## Konsekuensi

- Fungsi AI bisa diuji dan dijalankan lewat CLI tanpa DB.
- Backend memegang transaksi, idempotensi, dan validasi.
- Impor datar lewat `sys.path` (`paths.py`) dipakai agar backend memanggil modul tanpa paket terpisah; file spesifik fitur diberi prefiks untuk menghindari bentrok nama.
- Regenerasi satu blok atau satu soal juga lewat backend: backend mengirim data blok + feedback guru, AI mengembalikan teks baru, backend yang memperbarui DB.
