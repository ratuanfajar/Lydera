# 0005. Format prompt seragam dan klasifikasi gambar tiga percobaan di Annoter

- Status: diterima
- Tanggal: 2026-10

## Konteks

Prompt anotasi berupa satu paragraf per modul. Hasil rumus perlu lebih setia (83,7% pada 120 LaTeX unik), dan semua gambar diperlakukan sama padahal sekitar 20% hanya dekorasi (ikon, bingkai) yang tidak perlu dibacakan kepada siswa tunanetra. Bukti dan A/B ada di `docs/research/0002-ab-prompt-annoter.md` dan `0003-klasifikasi-gambar-annoter.md`.

## Keputusan

- Semua prompt Annoter berformat heading `# ROLE`, `# TASK`, `# CONTEXT`, `# RULES`, `# OUTPUT FORMAT`, `# EXAMPLES` lewat `common/prompt_format.build_prompt`; pesan user lewat `build_input`. Teks prompt hanya di `annoter/prompts.py`.
- Teknik per komponen: teks/heading tanpa LLM; rumus few-shot 7 contoh (kesetiaan 97,1%); tabel dan gambar zero-shot dengan keluaran JSON terstruktur. Few-shot untuk gambar ditolak karena menjangkar panjang deskripsi.
- Gambar diklasifikasi tiga kali oleh model yang sama (`gpt-5.4-mini`): percobaan 1 tanpa konteks, percobaan 2 dengan teks tetangga maksimal 400 karakter, percobaan 3 sebagai penentu akhir yang melihat gambar, kedua hasil sebelumnya, dan alasannya. Jenis: `dekoratif`, `ilustrasi_konteks`, `geometri`, `grafik`, `diagram`, `teks_di_gambar`.
- Gambar dekoratif dengan keyakinan 4 atau lebih dari 5 dilewati (teks kosong). Keyakinan lebih rendah jatuh ke `ilustrasi_konteks` dengan prioritas review tinggi. Jenis lain dideskripsikan dengan prompt per jenis; jenis tidak pasti memakai prompt umum.
- `image_kind` disimpan di `blocks.image_kind` (migrasi `df1233eb1f8b`) dan tampil di preview guru. Blok dekoratif yang diregenerasi guru dilabeli ulang `ilustrasi_konteks`.
- `review_priority` gambar tinggi hanya bila klasifikasi tidak pasti, deskripsi kosong, atau jenis grafik/diagram/teks_di_gambar.

## Konsekuensi

- Uji pada 109 gambar bab Lingkaran: prompt per jenis tidak terbukti lebih baik daripada prompt umum; user memutuskan tetap dipakai untuk produksi. Manfaat nyata: melewati sekitar 21% gambar dekoratif dan mencatat jenis untuk guru.
- Penentu akhir adalah model yang sama, bukan juri independen; salah klasifikasi masih mungkin (satu ikon dua kepala terklasifikasi geometri). Guru tetap meninjau.
- Tiga panggilan klasifikasi per gambar menambah biaya; hasilnya di-cache per percobaan.
- Prompt grafik dan teks di gambar: awalnya belum teruji; diuji terbatas pada bab 1 sampel (4 grafik, lihat F-029).
- Perubahan prompt atau model menginvalidasi cache lewat `PROMPT_VERSION` (kini 10).

## Pembaruan 2026-11-02: aturan bukti visual, gaya deskripsi, dan penanda tidak terbaca

Latar: usulan revisi prompt (annoter_prompt_revised.py) dan dua tinjauan (kode dan TalkBack) pada prompt gambar dan tabel. Bagian yang diambil ke `annoter/prompts.py`: `VISUAL_EVIDENCE_RULES` (hanya bukti visual, tidak menyimpulkan sejajar atau sama panjang dari bentuk, nilai tertulis dibedakan dari perkiraan, titik tanpa label tidak disebut pusat), `DESCRIPTION_STYLE_RULES` (kalimat pertama langsung menyebut jenis atau benda, simbol ditulis dengan kata, judul hanya bila tercetak, "tidak terbaca" hanya untuk teks atau angka yang ada tetapi kabur, label disebut sekali), nilai ekstrem grafik bersyarat, sel tabel "tidak terbaca" dibedakan dari sel kosong, skala skor klasifikasi 1 sampai 5, dan aturan arbiter. `PROMPT_VERSION` naik ke 11 dan `TABLE_PROMPT_VERSION` ke 4. Tidak diambil: entri `dekoratif` di `KIND_RULES` dan `ValueError` jenis tak dikenal (jenis dekoratif sudah dihentikan lebih awal di `image.py`).

Kode pendukung: sel "tidak terbaca" menambah temuan tabel dan deskripsi gambar yang memuat "tidak terbaca" atau "tidak dapat dibaca" menjadi prioritas review "high" ("tidak dapat dipastikan" sengaja tidak dihitung karena diminta aturan untuk hubungan geometri tanpa tanda); judul tabel berisi penanda kosong ("tidak ada", "-", dan sejenisnya) dinormalkan menjadi tanpa judul; regenerate rumus memakai prompt koordinat bila rumusnya memicu (ADR 0007).

Evaluasi (3 ulangan, tanpa cache, 31 gambar sampel bab 1 dan 2 dan 5 tabel, 93 deskripsi per versi; metrik objektif dan pemeriksaan ke gambar asli, tanpa juri LLM): stabilitas jenis gambar antar ulangan 27 dari 31 (lama) menjadi 30 sampai 31 dari 31 (baru), dan satu gambar yang pada versi lama sempat diklasifikasikan dekoratif (deskripsi dibuang) kini stabil sebagai diagram. Setelah aturan gaya ditambahkan: pembuka terlarang ("gambar", "pada gambar", "terlihat", "tampak", "terdapat") 17 menjadi 0 (lama 11 sampai 12), deskripsi bersimbol (garis miring, tanda kutip, pangkat) 21 menjadi 8 (lama 16 sampai 17; sisanya satuan seperti m/s yang disalin dari label dan tanda kutip pada teks gambar), deskripsi bertanda "tidak terbaca" 6 menjadi 1 (lama 0), panjang rata-rata 3,5 kalimat (lama 3,6), markdown 0. Pada grafik tekanan terhadap ketinggian, skala sumbu yang tertulis di buku (0, 5.000, 10.000, 15.000, 25.000, 30.000, tanpa 20.000) kini disebut persis; versi lama meringkas dan mengarang judul dari label sumbu. Tabel: nilai sel identik antar ulangan pada 5 tabel; satu dari 31 ulangan baru menghasilkan struktur tabel tidak valid pada tabel kosong berkolom huruf Yunani (8 ulangan tambahan semuanya valid), dan jalur cadangan teks tetap berlaku.

Batas: sampel hanya bab 1 dan 2 buku Kemendikdasmen kelas XI (1 tabel dengan sel gabungan atau rumus, jenis grafik terbatas); angka dihitung dari 3 ulangan sehingga selisih kecil bukan bukti; satuan majemuk bergaris miring (m/s) dan tanda kutip pada teks gambar belum bersih; belum ada uji dengar; anotasi bab yang sudah di DB tetap versi lama sampai dianotasi ulang.

## Pembaruan 2026-11-02 (lanjutan): penjaga deterministik pasca-model

Aturan prompt tidak menjamin kepatuhan model: satuan 'm/s' dan tanda kutip tetap muncul di deskripsi gambar walau dilarang. Karena itu `annoter/speakable.py` membersihkan deskripsi gambar setelah teks model dibaca dari cache (cache dan `PROMPT_VERSION` tidak berubah): kutip dibuang (aksen titik seperti A' dipertahankan), satuan ber-garis miring dibaca 'per', pecahan angka dibaca 'per', minus dan pangkat angka murni dibaca dengan kata, superskrip dan simbol relasi diganti kata. Prinsipnya konservatif (dipersempit lagi setelah audit bias sampel, F-061: f-1, '0 s', dan satuan tak dikenal dibiarkan mentah; 'per' hanya bila kedua sisi satuan sekolah umum, melibatkan angka, atau dua huruf tunggal; `PROMPT_VERSION` 12 setelah daftar istilah geometri khusus lingkaran diganti istilah umum, belum dievaluasi): pola ambigu (pangkat bukan angka murni, tanggal, bilangan campuran, kurung bergaris miring) dibiarkan mentah agar ditandai `description_issues`, karena salah ganti lebih buruk daripada mentah yang ditandai. Elipsis '...' dibiarkan apa adanya (keputusan user: bisa berupa soal isian).

Penjaga lain: `Breaker` memutus panggilan LLM setelah 5 galat sistemik beruntun dan dibagi antar window sehingga job gagal cepat dengan `AnnotationFailure`; blok gagal disimpan kosong berprioritas tinggi; `run_with_report` menyampaikan jumlah blok perlu ditinjau ke pesan job; tabel ditandai bila angka OCR hilang dari sel (tidak dipakai pada regenerasi); regenerasi rumus dan gambar kini diperiksa dengan pemeriksa yang sama seperti anotasi awal.

Putaran utuh bab 1 sampel dengan kode final (1 ulangan, output MinerU yang sudah ada): 172 blok, 0 gagal, penanda baru tidak menambah blok berprioritas tinggi di luar jenis grafik, diagram, dan teks_di_gambar; satuan ber-garis miring pada judul kolom tabel ditemukan lolos lalu dibersihkan dengan `speakable` pada sel tabel. Batas: satu bab dan satu ulangan; bacaan rumus lama di cache tidak diperiksa ulang oleh checker baru tanpa menaikkan `FORMULA_PROMPT_VERSION`; pembersih tidak menggantikan uji dengar.

