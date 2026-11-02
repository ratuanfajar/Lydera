# 0003. Klasifikasi gambar Annoter: apakah prompt per jenis lebih baik

- Tanggal: 2026-10-27
- Status: selesai. Rekomendasi saya: penyaring dekoratif + prompt umum. Keputusan user (2026-10-27): prompt per jenis (varian C) tetap diterapkan untuk produksi.
- Keyakinan: sedang (satu bab, dua juri yang tidak selalu sepakat, tanpa data grafik dan teks di gambar)

## Pertanyaan

Apakah mengklasifikasi gambar ke jenis (dekoratif, ilustrasi konteks, geometri, grafik, diagram, teks di gambar) lalu memakai prompt per jenis lebih baik daripada satu prompt umum, dan apakah gambar dekoratif perlu diinterpretasikan?

## Konteks Lydera

Gambar dari buku Matematika Kelas XI bab Lingkaran (109 gambar). Pembaca layar siswa tunanetra; ringkas, fokus pada data, tanpa informasi tak relevan.

## Temuan

Pedoman:
- W3C WAI: gambar dekoratif diberi teks alternatif kosong (kebisingan suara); informatif cukup deskripsi singkat; grafik dan diagram kompleks butuh ringkasan lalu deskripsi panjang; gambar berisi teks harus mencantumkan teksnya. Dekoratif atau informatif adalah penilaian penulis.
- DIAGRAM Center / NCAM: ringkas, fokus pada data, jelas, ringkasan dulu lalu rincian; "jika gambar tidak mengajarkan apa pun, perlakukan sebagai dekoratif".

Data bab Lingkaran:
- Distribusi 109 gambar: geometri 66, dekoratif 25, ilustrasi konteks 16, diagram 2, grafik 0, teks di gambar 0.
- Klasifikasi stabil: 108 dari 109 sama pada dua kali jalan; keyakinan 5 dari 5 pada 95%.
- Konteks teks: tanpa konteks versus teks tetangga langsung berbeda pada 6 gambar; konteks luas (3 blok kiri-kanan) menurunkan dekoratif dari 26 ke 19 dengan banyak ikon salah naik menjadi "ilustrasi konteks". Pada 8 ikon dekoratif (verifikasi visual oleh saya): tanpa konteks benar 7, tetangga langsung 6, konteks luas 1.
- Hanya 12 dari 109 gambar punya caption (7 bernomor) dan 2 dari 298 blok teks menyebut "Gambar <angka>"; relasi gambar-soal tidak bisa dideteksi lewat nomor.

Tiga varian, 109 gambar (model `gpt-5.4-mini`, effort `none`):
- A: satu prompt umum (aturan semua jenis di satu prompt).
- B: satu panggilan, model mengisi `jenis` lalu `deskripsi` (semua aturan jenis dalam satu prompt).
- C: dua tahap, klasifikasi dua kali (tanpa konteks dan dengan teks tetangga), dilewati bila keduanya dekoratif, lalu prompt khusus jenis.

| | A | B | C |
|---|---|---|---|
| Panggilan | 109 | 109 | 306 |
| Token masuk / keluar | 104 ribu / 27 ribu | 132 ribu / 16 ribu | 186 ribu / 27 ribu |
| Dilewati | 0 | 23 | 21 |

Ke-23 gambar yang dilewati (verifikasi visual): semuanya lencana penanda bagian buku atau kode QR; tidak ada gambar penting yang terbuang. C sengaja lebih konservatif (2 lencana ambigu tetap dideskripsikan).

Penilaian buta pada 40 gambar non-dekoratif (26 geometri, 12 ilustrasi konteks, 2 diagram), dua urutan A/B, 80 penilaian per pasangan per juri:

| Pasangan | Juri | A menang | Varian lain menang | Seri | Klaim salah A / lain |
|---|---|---|---|---|---|
| A vs B | gpt-5.4 | 48 | 28 | 4 | 32 / 26 |
| A vs B | grok-4.3 | 51 | 26 | 3 | 31 / 31 |
| A vs C | gpt-5.4 | 29 | 38 | 13 | 29 / 24 |
| A vs C | grok-4.3 | 38 | 32 | 10 | 20 / 32 |

Panjang rata-rata deskripsi: A 326, B 280, C 289 karakter.

## Inferensi

- Satu panggilan dengan semua aturan jenis (B) lebih buruk dari prompt umum: aturan jenis yang berdesakan menurunkan kualitas.
- Prompt per jenis (C) tidak menunjukkan keunggulan kualitas yang konsisten atas prompt umum pada bab ini (gabungan A 67, C 70, seri 23; klaim salah A 49, C 56), sedangkan biayanya 1,6 kali token.
- Manfaat nyata klasifikasi adalah melewati gambar dekoratif (sekitar 20% gambar) dan mencatat jenis untuk guru.

## Rekomendasi

Penyaring dekoratif + prompt umum (A): dua klasifikasi ringan (tanpa konteks dan dengan teks tetangga langsung), gambar dilewati hanya bila keduanya "dekoratif"; selain itu dideskripsikan dengan prompt umum yang sudah ada; jenis hasil klasifikasi disimpan sebagai `image_kind`. Prompt per jenis ditunda sampai ada data grafik, diagram, dan teks di gambar dari bab lain.

## Belum diverifikasi

Grafik dan teks di gambar tidak ada di sampel; biaya penuh varian D belum diukur; kebenaran dekoratif dinilai visual oleh saya, bukan oleh guru; hanya satu penerbit dan satu bab.

## Tindak lanjut

Implementasi penyaring dekoratif, kolom `image_kind` (migrasi), tinjau guru untuk blok dekoratif.

## Keputusan dan implementasi

User memutuskan varian C (klasifikasi, prompt khusus jenis) diterapkan untuk produksi meskipun hasil uji tidak menunjukkan keunggulan kualitas atas prompt umum, lalu mengubah klasifikasi menjadi tiga percobaan. Diterapkan di `annoter/image.py`:
- Percobaan 1 tanpa konteks, percobaan 2 dengan teks tetangga langsung (maksimal 400 karakter), percobaan 3 (penentu akhir) menerima gambar, kedua hasil sebelumnya beserta alasannya, lalu memutuskan jenis final. Ketiganya di-cache per gambar.
- Dilewati (teks kosong) hanya bila keputusan final `dekoratif` dengan keyakinan paling sedikit 4 dari 5. Bila keyakinan lebih rendah: diperlakukan `ilustrasi_konteks`, dideskripsikan dengan prompt umum, dan `review_priority` tinggi.
- Jenis yang valid dan yakin memakai prompt khusus jenis (ilustrasi konteks, geometri, grafik, diagram, teks di gambar); selain itu prompt umum.
- `image_kind` dikeluarkan di `annotated.json`, di preview guru, dan tersimpan di `blocks.image_kind` (migrasi `df1233eb1f8b`). Blok dekoratif yang diregenerasi guru dilabeli ulang `ilustrasi_konteks`.
- `review_priority` gambar: tinggi bila klasifikasi tidak pasti, deskripsi kosong, atau jenis grafik/diagram/teks di gambar; selain itu normal (aturan lama "tanpa caption = tinggi" dihapus).
- Verifikasi jalur produksi (tiga percobaan) pada 109 gambar: ilustrasi_konteks 16, dekoratif 23 (dilewati), diagram 3, geometri 67; 0 tidak pasti, 0 deskripsi dengan markdown. Dibanding dua percobaan sebelumnya, 4 gambar berubah: 2 menjadi dekoratif (ikon "?" benar; ilustrasi tutup/sirip merah meragukan), 2 menjadi geometri (bumi dengan titik dan garis wajar; ikon dua kepala dalam lingkaran salah, seharusnya ilustrasi). Prompt grafik dan teks di gambar aktif tetapi belum teruji (tidak ada contoh di bab ini).
