# 0002. A/B prompt Annoter: format seragam, rumus few-shot, masukan gambar

- Tanggal: 2026-10-27
- Status: selesai (dipakai di `ai-services/annoter/prompts.py`, `PROMPT_VERSION` 9)
- Keyakinan: sedang (juri LLM berisik; sampel kecil untuk gambar)

## Pertanyaan

Apakah prompt berformat seragam (`# ROLE`, `# TASK`, `# CONTEXT`, `# RULES`, `# OUTPUT FORMAT`, `# EXAMPLES`) dengan aturan per komponen lebih baik daripada prompt lama (satu paragraf, v6), dan teknik apa untuk rumus (zero-shot atau few-shot)?

## Konteks Lydera

Annoter harus mengubah rumus, tabel, dan gambar menjadi teks linear untuk TalkBack tanpa menghilangkan informasi dan tanpa detail berlebihan. Model: `gpt-5.4-mini`, effort `none`. Sampel dari bab Lingkaran (Kelas XI): 120 LaTeX unik (5 blok rumus, inline `$..$`, dan 14 ekspresi sintetis SMA di luar contoh few-shot), 14 gambar acak (seed tetap), 1 tabel.

## Temuan

Rumus (juri `grok-4.3`, keluarga berbeda dari generator; 2 kali jalan per varian; setia = semua simbol terbaca berurutan, makna benar):

| Varian | Setia | Ambigu | Identik antar-ulangan |
|---|---|---|---|
| Prompt lama v6 (cache) | 81,0% sampai 83,7% (dua putaran juri) | 2,9% | - |
| Zero-shot baru | 94,5% | 1,7% | 79/120 |
| Few-shot baru, putaran 1 | 96,2% | 2,1% | 88/120 |
| Few-shot baru, aturan direvisi | 97,1% | 0,0% | 102/120 |

- Nama huruf Yunani konsisten (`alfa`, `teta`); prompt lama memakai `alpha` (2 kali).
- Kegagalan yang ditemukan lalu diperbaiki lewat aturan: pecahan multi-suku ambigu ("x dikurangi tiga per dua"), `\widehat` terbaca "sudut" (seharusnya busur), `\overline` terbaca "garis di atas" (seharusnya ruas garis), kurung kurawal pengelompokan terbaca "buka kurung", `\cdot` terbaca "komposisi", koma penutup ekspresi terbaca "koma". Cek ulang 8 kasus (3 kali jalan): semua benar kecuali satu kali pada "250.000" hasil OCR.
- Sisa kegagalan yang diterima: `\overbrace` (jarang), struktur `array` dengan baris kosong.

Gambar dan tabel (juri `gpt-5.4` buta, dua urutan A/B per sampel, 15 sampel, 30 penilaian; lama = cache v6):

| Putaran | Baru menang | Lama menang | Seri | Klaim salah (baru / lama) |
|---|---|---|---|---|
| 1 (tugas "untuk mengerjakan soal") | 12 | 17 | 1 | - |
| 2 (tugas ditulis ulang, tanpa instruksi akhir) | 15 | 14 | 1 | 18 / 20 |
| 3 (teks sekitar diberi label bukan-isi + instruksi akhir) | 18 | 9 | 3 | 7 / 24 |

Juri kedua untuk gambar (putaran 3 dinilai ulang oleh `grok-4.3`, keluarga berbeda dari generator; pasangan dan urutan A/B sama; 30 penilaian):

| Juri | Baru menang | Lama menang | Seri | Klaim salah (baru / lama) |
|---|---|---|---|---|
| `gpt-5.4` (keluarga sama dengan generator) | 18 | 9 | 3 | 7 / 24 |
| `grok-4.3` (keluarga berbeda) | 12 | 15 | 3 | 10 / 14 |

- Kedua juri sepakat pada 18 dari 30 penilaian (60%). Total gabungan 60 penilaian: baru 30, lama 24, seri 6.
- Yang disepakati: prompt baru memuat lebih sedikit klaim salah (7 lawan 24, dan 10 lawan 14); prompt lama lebih baik pada kode QR (penanda sudut) dan roda bianglala; prompt baru lebih baik pada gambar geometri bertitik (#7, #10).
- Pada tabel kedua juri berbeda: `gpt-5.4` memilih baru, `grok-4.3` memilih lama. Saya memeriksa gambarnya langsung: ada baris judul (α, θ) dan 3 baris kosong. Prompt baru ("Baris 1 sampai 3 kosong") benar; prompt lama ("keempat baris kosong") salah. Jadi penilaian `grok-4.3` pada tabel keliru.
- Kesimpulan yang bisa dipertahankan: kualitas keseluruhan prompt baru setara dengan prompt lama (bergantung juri), sedangkan keunggulan yang konsisten adalah lebih sedikit klaim salah/halusinasi dan tabel yang benar, dengan deskripsi sekitar 9% lebih panjang. Format seragam dipertahankan karena tidak menurunkan kualitas.

- Putaran 1 gagal karena tugas "memuat informasi yang dibutuhkan untuk mengerjakan soal" mendorong model menyalin angka dan nama dari teks sekitar ke gambar yang tidak memuatnya, dan tidak ada aturan membaca teks yang tertulis di gambar (isi gelembung percakapan hilang).
- Halusinasi ikon bohlam menjadi "diagram titik A, B, C, D" muncul 2 dari 3 kali bila teks sekitar bertema geometri dan 0 dari 3 tanpa teks sekitar. Memberi teks sekitar heading `# SURROUNDING TEXT NOT IMAGE CONTENT` dan instruksi akhir `# INSTRUCTION` menghilangkannya (6 dari 6 benar pada dua tata letak yang diuji).
- Tabel: prompt baru membaca 3 baris kosong dengan benar; hasil lama mengklaim 4 baris.
- Panjang rata-rata deskripsi gambar: baru 212 karakter, lama 195 (putaran 3).

## Inferensi

Format berheading tidak merugikan; kualitas ditentukan oleh isi aturan dan tata letak masukan. Few-shot pada rumus aman (transkripsi deterministik, risiko jangkar rendah) dan memperbaiki konsistensi; pada gambar few-shot tetap dihindari karena catatan lama bahwa contoh memangkas detail.

## Opsi

| Opsi | Kualitas | Risiko |
|---|---|---|
| Prompt lama | sedang | bocor teks sekitar, nama Yunani Inggris |
| Zero-shot rumus | baik | kurang konsisten |
| Few-shot rumus (dipilih) | terbaik | prompt lebih panjang (sekitar 2,8 ribu karakter) |

## Rekomendasi

Pakai prompt baru: rumus few-shot (7 contoh), tabel dan gambar zero-shot terstruktur, aturan nama Yunani bersama, masukan gambar dengan label bukan-isi dan instruksi akhir.

## Belum diverifikasi

Juri LLM berisik dan dua juri gambar hanya sepakat 60% (contoh: `grok-4.3` keliru pada tabel, `gpt-5.4` sekeluarga dengan generator); sampel gambar hanya 14 dan satu tabel (hanya bab Lingkaran); belum dibandingkan dengan penilaian manusia atau siswa tunanetra; biaya per bab penuh belum diukur ulang dengan prompt baru.

## Tindak lanjut

Uji manual oleh guru atau siswa pada hasil anotasi bab penuh; ukur biaya bab penuh sebelum merilis.
