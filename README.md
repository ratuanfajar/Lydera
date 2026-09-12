# Lydera

Aplikasi mobile yang memfasilitasi pembelajaran matematika bagi siswa tunanetra dan guru mereka, mencakup seluruh tahap belajar: penyiapan modul, pembelajaran, dan asesmen.

## Tentang

Lydera menjembatani supaya modul dan soal matematika bisa diakses penuh oleh siswa tunanetra lewat pembaca layar (talkback), tanpa kehilangan makna matematisnya — rumus, tabel, dan gambar/grafik diterjemahkan jadi teks oleh AI, bukan sekadar dibaca literal atau di-OCR apa adanya. Setiap keluaran AI divalidasi guru sebelum sampai ke siswa, sehingga materi tetap sesuai kurikulum dan keputusan akhir tetap ada di tangan guru.

## Untuk Siapa

- **Siswa tunanetra** — pengguna utama, belajar matematika secara mandiri lewat pembaca layar.
- **Guru matematika sekolah luar biasa (SLB)** — mengelola modul dan membuat soal ujian dari modul yang diunggah.

## Fitur

### Annoter — Anotasi Modul
Guru upload modul matematika per bab. Sistem mengekstrak isinya (termasuk rumus, tabel, gambar/grafik) dan mengubahnya jadi teks siap dibacakan pembaca layar — rumus diverbalisasi, tabel dilinearisasi, gambar dideskripsikan lewat AI. Guru memvalidasi hasilnya sebelum dibagikan ke siswa; bagian yang salah bisa digenerate ulang lewat feedback guru.

### Quizzer — Quiz Generator
Guru pilih modul dan bab (bisa lebih dari satu sekaligus), lalu tentukan jumlah soal LOTS dan HOTS untuk tiap bab. Sistem menghasilkan soal pilihan ganda beserta langkah penyelesaian dan kesimpulan jawaban, digroundkan ke isi modul yang sudah dianotasi, tanpa menyalin ulang soal latihan yang sudah ada di modul. Soal mengikuti Capaian Pembelajaran (CP) Kurikulum Merdeka sesuai fase modul, dengan level taksonomi Bloom sesuai LOTS (C1-C3)/HOTS (C4-C6). Tiap soal dicek ulang otomatis sebelum sampai ke guru: AI menjawab ulang soal itu secara independen dari materi yang sama dan menandai kalau hasilnya tidak konsisten dengan jawaban aslinya. Guru memvalidasi tiap soal; koreksi soal LOTS (berdiri sendiri) dilakukan guru langsung, sedangkan soal HOTS (punya stimulus/konteks bersama) dikoreksi lewat feedback ke AI yang meregenerasi ulang, dan guru approve hasilnya sebelum final.

Hasil kedua fitur di atas tersimpan ke database yang sama, dan sama-sama diakses siswa lewat aplikasi yang aksesibel untuk pembaca layar.

## Alur Singkat

```
Guru upload modul per bab
    -> sistem ekstrak & anotasi (rumus/tabel/gambar -> teks siap-talkback)
    -> guru validasi, revisi kalau perlu
    -> siswa akses modul lewat pembaca layar

Guru pilih bab + jumlah soal LOTS/HOTS
    -> sistem generate soal pilihan ganda (digroundkan ke modul yang sudah dianotasi)
    -> guru validasi, edit langsung kalau ada yang salah
    -> siswa kerjakan quiz lewat pembaca layar
```

## Arsitektur

Tiga bagian, dikembangkan dan dijalankan terpisah:

| Bagian | Tanggung jawab | Dokumentasi |
|---|---|---|
| Layanan AI | Ekstraksi PDF (MinerU), anotasi rumus/tabel/gambar dan generate soal (LLM/MLLM) | [`ai-services/README.md`](ai%20services/README.md) |
| Backend | Penyimpanan (PostgreSQL), API (FastAPI), orkestrasi pemrosesan bab | [`backend/README.md`](backend/README.md) |
| Frontend | Aplikasi guru (upload, validasi) dan siswa (akses modul/quiz lewat pembaca layar) | [`frontend/README.md`](frontend/README.md) |.
