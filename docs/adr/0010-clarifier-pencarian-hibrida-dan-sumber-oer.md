# 0010. Clarifier: pencarian hibrida dan sumber luar OER saja

- Status: diterima; bagian chunk digantikan oleh [0015](0015-chunk-clarifier-berbasis-ukuran.md) (2026-11-03)
- Tanggal: 2026-10-28

## Konteks

Clarifier menjawab pertanyaan siswa tunanetra dari modul yang dianotasi guru. Pencarian modul hanya memakai kemiripan vektor pada teks lafal, sehingga pertanyaan yang menyalin persamaan persis sering meleset, dan LaTeX asli di `blocks.source_markup` tidak ikut diindeks. Sumber luar mencakup web umum dan Wolfram, dan sumber tier 3 (bucket S3, blog) lolos ke jawaban dengan sitasi berstatus terverifikasi (F-014). Spec: [0005](../specs/0005-clarifier-pencarian-hibrida-dan-sumber-oer.md). Dasar sumber luar: [riset 0001](../research/0001-filter-sumber-web-clarifier.md).

## Keputusan

- **Tiga daftar kandidat digabung RRF berbobot** (k = 60): vektor (cosine, bobot 1,0), kata kunci (`tsvector` konfigurasi `simple`, bobot 0,25), dan kecocokan rumus persis (bobot 2,0, hanya bila kueri memuat rumus). `similarity` tiap hasil tetap cosine; `scope_gate` memakai nilai tertinggi; chunk dengan cosine tertinggi selalu ikut dalam hasil.
- **Rumus dicocokkan sebagai substring persis pada bentuk kanonik**, bukan trigram. `pg_trgm` mengabaikan tanda baca sehingga `x^2-5x+6` dan `x^2+5x+6` tidak terbedakan. Bentuk kanonik (`formula_text.normalize_formula`) membawa LaTeX buku dan ketikan siswa ke bentuk yang sama: huruf kecil tanpa spasi, `\frac{a}{b}` dan `a/b` menjadi `(a)/(b)`, `x^{2}` dan `x²` menjadi `x^2`, pangkat multi-digit menjadi `^(10)`. Rumus kueri diambil dengan `formula_spans` (panjang kanonik minimal 5 karakter dan memuat operator). Teks yang di-embed tetap teks lafal.
- **Token kata kunci hanya yang jarang**: token yang muncul di lebih dari 10% chunk kelas (atau lebih dari 2 chunk pada kelas kecil) dibuang, karena tanpa itu istilah umum seperti "fungsi" membuat `ts_rank_cd` menaikkan chunk panjang dan hibrida lebih buruk daripada vektor saja.
- **Chunk**: section di bawah heading dipecah di batas blok pada 1.500 karakter; section yang heading atau isinya memuat ISBN, "Dilarang memperbanyak", atau "Hak Cipta Dilindungi" dilewati. Tiap chunk menyimpan `formula_norm` (rumus blok formula dan potongan `$...$`, dipisah `;`).
- **Data**: `block_embeddings.lexical_tsv` (kolom generated dari `chunk_text`, indeks GIN) dan `formula_norm`; migrasi `c3d97c01e878`. `CREATE EXTENSION IF NOT EXISTS vector` dan `pg_trgm` ditambahkan di migrasi pertama `7687613b2cdc` (F-003). Cache retrieval memuat versi pencarian, kelas, `top_k`, dan kueri (C-003).
- **Sumber luar hanya `search_oer`** ke enam host persis (`murid.kemendikdasmen.go.id`, `repositori.kemendikdasmen.go.id`, `openstax.org`, `www/id/en.khanacademy.org`), ditegakkan di `include_domains` dan di kode (host persis, skema https), dengan hasil berskor di bawah `OER_MIN_SCORE` dibuang. Ambang awal 0,7 diturunkan ke 0,6 atas keputusan user setelah pengukuran di bawah. Wolfram, `search_academic_web`, tier, dan `trust_tier` dihapus. Parameter `subject` dihapus karena menempelkan "matematika" ke kueri menurunkan skor (satu kueri uji: 0,75 menjadi 0,34).
- **Sitasi**: `reference` sumber `oer` yang tertukar satu-dua karakter dengan URL hasil tool (kemiripan >= 0,97) dipetakan ke URL itu, dan `reference` dikoreksi hanya bila kutipan lolos verifikasi. Kunci angka hanya untuk sumber `modul` dan kunci URL hanya untuk `oer`.
- **Prompt**: aturan penulisan untuk pembaca layar ditambahkan (tanpa simbol matematika mentah, tanpa pembuka meta, tanpa singkatan, tanpa kutipan Inggris, tiap kalimat sekitar 25 kata), dan deskripsi `label`, `justification`, `summary` diperketat. Respons API: `sources[].trust_tier` dihapus.

## Hasil evaluasi (DB dev; bab 1 dan 2 dimuat sebagai modul uji, 147 chunk; penilai: kecocokan dengan chunk sumber)

| Ukuran | Vektor saja | Vektor + kata | Hibrida |
|---|---|---|---|
| `dataset.json` 17 pertanyaan: recall@5 | 14/17 | 14/17 | 14/17 |
| `dataset.json`: MRR | 0,794 | 0,750 | 0,750 |
| `formula_queries.json` 14 pertanyaan rumus persis: recall@5 | 13/14 | 14/14 | 14/14 |
| `formula_queries.json`: MRR | 0,475 | 0,469 | 1,000 |
| 2 kontrol negatif: kandidat rumus | - | - | 0 dan 0 |
| `scope_gate`, klasifikasi 17 pertanyaan, 3 ulangan | - | - | identik dengan vektor saja |

- Percobaan pertama tanpa penyaringan token jarang: recall@5 `dataset.json` hibrida 13/17 (di bawah vektor saja); bobot sama rata (1, 1, 1) setelah penyaringan: MRR 0,711. Bobot (1, 0,25, 2) dipilih dari lima kombinasi pada kedua kumpulan yang sama, jadi angka MRR 0,750 dan 1,000 dituning pada data yang dipakai untuk menilai.
- Kata kunci tidak menambah recall pada `dataset.json` dan menurunkan MRR sedikit (0,794 menjadi 0,750). Manfaat terukurnya hanya pada pertanyaan rumus (13/14 menjadi 14/14). Bobot rendah mempertahankannya sebagai jaring pengaman untuk istilah persis; bila bukti ini tidak bertambah, kolom dan indeks tsvector layak dicabut.
- Pertanyaan rumus saya salin dari buku (14 dari bab 1 dan 2) dan ditentukan chunk sumbernya dari isi bab, bukan keluaran kode, tetapi rumusnya cocok persis dengan buku; ketikan siswa yang menyimpang (urutan suku lain, spasi atau tanda berbeda) tidak diuji, dan bergantung pada vektor dan kata kunci.

Sumber luar (Tavily, 12 kueri, 60 hasil mentah): pada ambang 0,7 lolos 13 hasil dan 4 dari 10 kueri perluasan menghasilkan sumber; pada ambang 0,6 lolos 21 hasil dan 7 dari 10 kueri menghasilkan sumber. Dua kueri di luar topik tetap nol di kedua ambang, dan semua hasil lolos dari lima host. Hasil yang relevan terbuang pada ambang 0,7: fungsi invers 0,67/0,67/0,65, barisan aritmetika 0,66, persamaan lingkaran 0,63, aturan sinus dan cosinus 0,59 (judul tepat), komposisi fungsi 0,49; skor di bawah 0,4 tidak relevan. Pada ambang 0,6, 3 ulangan live atas 7 pertanyaan (21 jawaban) menghasilkan 0 jawaban dengan simbol mentah dan 0 galat; fungsi invers mendapat sumber luar pada 1 dari 3 ulangan (sitasinya tidak terverifikasi pada 1 dari 2 sumber luar yang muncul), persamaan lingkaran 3 dari 3, dan rumus suku ke-n barisan aritmetika serta notasi sigma ditolak `scope_gate` atau berakhir "tidak ditemukan" karena modul uji hanya memuat fungsi dan lingkaran. Pada ambang 0,7, dalam 3 ulangan live (3 pertanyaan perluasan), sitasi terverifikasi pada sebagian besar jawaban, tetapi jawabannya tipis karena cuplikan `murid.kemendikdasmen.go.id` hanya deskripsi satu kalimat video atau lab (F-048, F-049). Setelah aturan penulisan ditambahkan, 10 jawaban live (2 ulangan x 5 pertanyaan) tidak memuat simbol mentah; sebelumnya "f o g", "(f + g)(x)", "P(a, b)", dan "O(0,0)" lolos.

## Konsekuensi

- **Reindex wajib setelah migrasi.** `formula_norm` bernilai kosong untuk chunk lama sampai bab di-reindex; jalur rumus kosong, jalur lain tetap bekerja. Reindex memanggil API embedding dan menulis `block_embeddings`.
- **Sumber luar dangkal, dan itu batas sumber.** Pengukuran lanjutan (F-048): halaman `murid.` berskor tinggi adalah halaman video atau lab yang tidak dapat diambil (Tavily extract gagal, `raw_content` kosong), dan halaman interaktif hanya berisi blurb; cuplikan Khan Academy sudah relevan. Jadi mengambil teks halaman tidak menambah isi. Jawaban perluasan sering berbentuk "sumber hanya menyebut materi ini membahas ..., tetapi tidak memuat rumusnya". Itu jujur tetapi kurang berguna. Ambang sudah diturunkan ke 0,6. Isi sumber luar diperkaya dengan menambah `repositori.kemendikdasmen.go.id` (lihat bagian berikut).
- Ambang sensitif pada rumusan kueri yang ditulis ulang model; hasil live tidak deterministik antar ulangan.
- Kutipan dari Khan Academy dan OpenStax bisa berbahasa Inggris; prompt meminta ringkasan dan justifikasi tetap Indonesia, tetapi `evidence` mengikuti sumber (diverifikasi kata demi kata). Catatan untuk frontend: `reference` URL panjang jangan dibacakan per karakter (label semantik pendek, tautan sebagai aksi), dan evidence berbahasa Inggris diberi penanda bahasa.
- Pencarian belum memfilter baris `deleted_at` (modul, bab, embedding); perilaku lama, dan aplikasi memakai penghapusan keras untuk modul.
- Alternatif yang ditolak: trigram (menyamakan tanda `+` dan `-`), wildcard TLD (ditolak API, riset 0001), tier kepercayaan (meloloskan sumber tier 3).

## Pembaruan: `repositori.kemendikdasmen.go.id` ditambahkan (keputusan user, sampel bab 1)

Pengukuran: 9 pertanyaan bab 1 (fungsi, komposisi, invers) dari `dataset.json`, ambang 0,6. Daftar lima host lama meloloskan 4 hasil; `repositori` saja meloloskan 32 hasil, hampir semuanya relevan dan berupa cuplikan 2.000 sampai 2.400 karakter (modul KD 3.5 dan 3.6 kelas X, "Modul SMA KK B", "Matematika Kelas X dan XI"), dibanding 120 sampai 170 karakter pada `murid.`. Satu pertanyaan (relasi dan representasinya) tetap tanpa hasil.

Uji live (modul lingkaran, 3 ulangan x 3 pertanyaan perluasan, 0 galat, 0 simbol mentah): persamaan lingkaran, persamaan garis singgung dengan gradien, dan sudut dalam dan luar kini dijawab dengan rumus utuh dari sumber, dengan sitasi terverifikasi. Sebelum penambahan, jawaban yang sama hanya berbunyi "sumber menyebut materi ini membahas ...".

Risiko yang ditemukan dan penanganannya:
- Teks PDF memuat karakter font simbol (U+F06F, U+F0AE, dan sejenisnya, area private-use) di tempat simbol matematika; `external_tools._clean` menggantinya dengan spasi sebelum cuplikan sampai ke model.
- Cuplikan PDF sering memotong atau mengacak rumus. Aturan prompt ditambahkan: rumus disampaikan hanya bila tertulis utuh, istilah tidak diganti, dan bagian yang belum ada disebut. Aturan ini tidak mengubah hasil pada tiga pertanyaan uji awal; manfaatnya baru terlihat pada putaran review berikut.
- Isi modul ini ditulis untuk guru dan bisa memakai kurikulum lama atau kata yang tidak tepat. Contoh nyata: modul SMP menulis "sudut luar sama dengan setengah selisih antara sudut keliling yang menghadap kedua busur"; maksudnya besar busur. Model menyampaikan kalimat itu setia (`verified` benar) dan jawaban live pada 2 dari 3 ulangan mengulang istilah "sudut keliling", pada ulangan lain "sudut pusat". Jadi verifikasi sitasi menjamin kesetiaan pada sumber, bukan kebenaran sumber.
- Satu hasil berskor di atas ambang berasal dari modul kelas VII dan tidak relevan; keputusan memakainya ada pada model.

## Pembaruan: review ketiga (kode dan TalkBack) dan modul bab 1 sampel

Perubahan:
- Prompt: aturan data bukan instruksi untuk isi hasil tool, aturan isian kosong dari buku (jangan diisi dari pengetahuan umum), aturan sumber luar bisa salah tulis (jangan diperbaiki sendiri, utamakan modul, sarankan cek ke guru), kalimat penutup bila inti jawaban dari sumber luar, aturan pengelompokan rumus dan kata operasi tetap, satuan lengkap ("kilometer per jam"), tanpa URL atau nama berkas, batas panjang (tiga kalimat inti, kalimat rumus sampai sekitar 40 kata). Aturan "jangan mengganti istilah" dihapus karena justru memelihara kesalahan sumber.
- Kode: cuplikan yang kosong setelah dibersihkan dibuang; konten `null`, JSON bukan objek, dan URL rusak tidak merusak giliran chat; cuplikan URL yang sama dari dua panggilan digabung, bukan ditimpa; verifikasi sitasi mewajibkan setiap angka di `evidence` ada di sumber; `evidence` diminta berupa kalimat narasi utuh; deskripsi `search_oer` dan contoh `label` memuat Repositori.
- Env: nilai kosong atau hanya spasi pada `SCOPE_SIM_*` dan `OER_MIN_SCORE` memakai default.

Hasil uji live (modul lingkaran dan bab 1 fungsi hasil ingest, 3 ulangan x 5 pertanyaan, 0 galat): sudut keliling pada diameter dijawab sembilan puluh derajat pada 3 dari 3 ulangan setelah aturan isian kosong (sebelumnya satu jawaban salah "setengah putaran", F-053); satuan terucap lengkap; jawaban tabel (69 meter) benar 3 dari 3. Pengelompokan rumus belum andal: "kuadrat dari selisih x dan h" muncul pada 2 dari 3 ulangan, satu ulangan "selisih x dan h kuadrat" yang masih ambigu (F-054). Satu ulangan garis singgung berakhir "tidak ditemukan" karena cuplikan yang kali itu terambil tidak memuat rumus dan verifikasi menolak evidence karangan; itu perilaku yang diinginkan.

Batas yang diketahui: `verified` tidak mencakup isi `summary` (F-055); sumber luar masih bisa salah (contoh sudut dalam dan luar), dan model hanya diminta, tidak dipaksa, melaporkannya; isian kosong buku hilang dari teks bacaan di hulu (F-053).
