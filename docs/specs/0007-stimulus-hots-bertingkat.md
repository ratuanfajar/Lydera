# 0007. Stimulus soal HOTS bertingkat: dari teks dan tabel sampai gambar berbasis data

- Status: disetujui; DIREVISI 2026-11-02 (jenis akhir: teks, tabel, gambar SVG, campuran; lihat "Status implementasi" dan ADR 0012; bagian rancangan jenis data per jenis di atasnya sudah digantikan)
- Tanggal: 2026-11-02
- ADR terkait: [0012](../adr/0012-stimulus-bertipe-data-dulu-render-di-klien.md). Dasar: [spec 0001](0001-pipeline-quizzer-plan-then-generate.md), [spec 0002](0002-soal-dengan-rumus-tabel-dan-gambar.md) (Fase B ditahan), [spec 0003](0003-tabel-dua-mode-baca.md), [ADR 0007](../adr/0007-verbalizer-rumus-gaya-kelas-dengan-pemeriksa-struktur.md), [ADR 0008](../adr/0008-tabel-dua-mode-baca.md)

## Masalah

Soal HOTS (C4 dan C5) Quizzer sekarang berstimulus teks. Stimulus berisi tabel dan LaTeX sudah dirancang (spec 0002 Fase A) tetapi mati selama `QUIZ_MARKUP_ENABLED` belum dinyalakan, dan stimulus bergambar belum ada (spec 0002 Fase B ditahan). Akibatnya banyak topik yang wajar diujikan lewat data, grafik, diagram, atau bangun geometri tidak bisa dibuat selain dengan cerita panjang. Guru dan partner pengembang sudah menyepakati cakupan bertahap: teks, tabel, LaTeX, dan dokumen kontekstual dulu; gambar berbasis kode sesudahnya; bangun ruang dan stimulus campuran paling akhir. Spec ini mengunci cakupan itu, prinsip desainnya, dan pintu aktivasi tiap jenis, supaya pekerjaan sebesar ini tidak menjadi satu rilis raksasa dan tidak merusak aksesibilitas.

Terdampak: siswa tunanetra (hanya membaca teks siap-baca, jadi seluruh informasi soal harus ada di teks), siswa low vision dan teman sekelas yang melihat (mendapat tampilan visual), dan guru yang meninjau soal.

## Prinsip

1. **Aturan jenjang tidak berubah.** Soal LOTS (C1 sampai C3) dirancang dapat dijawab langsung dari soal dan tidak punya stimulus; soal HOTS (C4 dan C5) wajib punya stimulus. Aturan ini sudah dipaksa kode (`quizzer/checks.stimulus_level_issue`, instruksi stimulus hanya untuk level 4 ke atas) dan tidak diubah.
2. **Jenis stimulus ditulis umum.** Daftar contoh (struk, jadwal, grafik batang, dan sebagainya) hanya hidup di dokumen ini. Prompt dan skema memakai jenis abstrak (teks, tabel, rumus, dokumen, grafik data, bidang koordinat, diagram relasi, geometri datar, bangun ruang, campuran) tanpa menyebut contoh, supaya model tidak condong ke contoh tertentu.
3. **Data lebih dulu, bukan kode.** Untuk jenis non-teks, LLM hanya menghasilkan spesifikasi data terstruktur (JSON) yang divalidasi skema. Kode menurunkan teks siap-baca secara deterministik dan merender gambar dari templat tetap. Kode, Mermaid, TikZ, SVG, atau matplotlib yang ditulis LLM tidak pernah dijalankan atau diterima mentah.
4. **Teks turunan harus lengkap sendiri.** Siswa tunanetra tidak melihat gambar. Setiap angka, label, titik, dan hubungan yang diperlukan untuk menjawab harus muncul di teks siap-baca yang diturunkan dari spesifikasi. Gambar tidak pernah menjadi satu-satunya pembawa informasi.
5. **Satu sumber kebenaran.** Teks dan gambar berasal dari spesifikasi yang sama sehingga tidak bisa berbeda. Kebenaran gambar dijamin renderer deterministik, bukan penilaian LLM.
6. **Pintu aktivasi per jenis.** Setiap jenis punya skema, pemeriksa kode, penurun teks, renderer (bila ada), tes, dan sampel yang dicek manual. Jenis dinyalakan satu per satu lewat konfigurasi.
7. **Ilustrasi hasil image generation dibuang dari rencana.** Hasilnya tidak deterministik, tidak memengaruhi jawaban, tidak berguna bagi pengguna utama, dan berisiko memuat konten tidak sesuai.

## Perilaku yang diharapkan

### Fase 1 (MVP): teks, tabel, rumus, dokumen

Jenis `teks`: kasus kontekstual atau narasi analisis (sudah ada).

Jenis `tabel`: data berbentuk daftar nilai, tabel terstruktur `{judul, kolom, baris}` yang dibaca kode (ADR 0008); bukan markdown mentah. Tampilan visual dibentuk dari struktur yang sama.

Jenis `rumus`: persamaan, matriks, dan ekspresi formal sebagai LaTeX inline; bacaannya diturunkan verbalizer (ADR 0007).

Jenis `dokumen`: dokumen kontekstual berbasis teks, dirender sebagai teks atau tabel (tidak ada mesin tata letak). Ini hanya pedoman jenis di prompt, bukan fitur baru di kode.

Perilaku:

1. Prompt generator mendeskripsikan jenis stimulus secara umum dan meminta model memilih jenis yang paling sesuai dengan poin materi, tanpa daftar contoh.
2. Soal yang perhitungannya bergantung pada data harus membawa data lengkap di stimulus (teks atau tabel). Pemeriksaan: validator buta mengerjakan soal hanya dari teks siap-baca; bila tidak bisa menjawab, soal ditandai.
3. `QUIZ_MARKUP_ENABLED` dinyalakan hanya setelah uji dengar dan pengukuran kesetiaan verbalizer pada rumus buatan LLM (prasyarat spec 0002).

### Fase 2: gambar berbasis data

Setiap jenis berikut memakai spesifikasi JSON, teks turunan oleh kode, dan templat render tetap.

| Jenis | Isi spesifikasi | Pemeriksa kode | Teks turunan |
|---|---|---|---|
| `grafik_data` (batang, garis, lingkaran, histogram) | subjenis, label dan satuan sumbu, seri dengan pasangan kategori atau x dan nilai; histogram berisi kelas dengan batas bawah, batas atas, frekuensi | panjang seri konsisten, nilai angka dan tidak negatif untuk batang, lingkaran, dan histogram; bagian lingkaran berjumlah total atau 100 persen; kelas histogram berurutan tanpa tumpang tindih | ringkasan lalu tabel data baris demi baris lewat linearisasi tabel yang sudah ada |
| `bidang_koordinat` dan `garis_bilangan` | rentang sumbu, titik bernama dengan koordinat, garis atau kurva dari daftar templat bernama dengan parameter (bukan ekspresi bebas), interval dengan batas termasuk atau tidak | titik dalam rentang, parameter templat valid, interval tidak terbalik | daftar titik dan persamaan dibacakan; interval dibacakan dengan kata |
| `diagram_relasi` (pohon peluang, himpunan, alur) | simpul dengan id dan label, sisi dengan label atau nilai; himpunan dengan elemen dan semesta | graf tanpa siklus untuk pohon, peluang cabang tiap induk berjumlah satu, elemen himpunan konsisten, irisan dan gabungan dihitung kode | penelusuran simpul demi simpul dengan peluang atau elemen; relasi himpunan dihitung kode, bukan oleh LLM |
| `geometri_datar` | bangun, parameter (panjang sisi, besar sudut, jari-jari), titik berlabel, hubungan yang dinyatakan (tegak lurus, sejajar, sama panjang) | LLM tidak memberi koordinat; kode menghitung koordinat dari parameter dan memeriksa konsistensi (ketaksamaan segitiga, jumlah sudut, hubungan yang dinyatakan terpenuhi) | label, ukuran, dan hubungan dibacakan; nama titik huruf demi huruf (aturan baca-lantang yang ada) |

Perilaku umum Fase 2:

1. Soal dan stimulus boleh merujuk "data berikut" atau "diagram tadi" hanya bila spesifikasi dan teks turunan menyertainya; larangan merujuk gambar (`TEXT_ONLY_RULE`, `checks.references_visual`) dilonggarkan hanya untuk jenis yang aktif dan hanya bila teks turunan memuat seluruh datanya.
2. Pemeriksaan kode "semua angka dalam spesifikasi muncul di teks turunan" wajib lolos sebelum soal disimpan.
3. Backend menyediakan dua hal per stimulus: bentuk ASLI (rumus LaTeX, tabel terstruktur, atau spesifikasi data untuk grafik, diagram, dan geometri) dan teks naratif siap-baca. Cara menyajikannya (menampilkan visual, membacakan, atau menelusuri) adalah urusan frontend. Guru diasumsikan dapat melihat, sehingga di tampilan Quizzer ia melihat yang asli dan boleh melihat atau mendengarkan teks naratifnya. Edit spesifikasi oleh guru menurunkan ulang teks naratif.
4. Validator LLM tidak menilai gambar (juri gambar hanya sepakat sekitar 60 persen). Validator buta mengerjakan soal dari teks turunan.

### Fase 3: bangun ruang dan stimulus campuran

1. `bangun_ruang`: hanya dari templat tetap yang berparameter (kubus, balok, prisma, limas) dan jaring-jaring dari daftar tetap. Teks turunan menyebut sifat bangun (jumlah sisi, rusuk, titik sudut) dari templat. Dikerjakan paling akhir, setelah geometri datar stabil.
2. `campuran`: satu stimulus berisi daftar komponen berurutan dari jenis yang sudah aktif; tiap komponen divalidasi sendiri dan teks siap-baca digabung berurutan. Bukan jenis baru dalam arti renderer.

## Di luar cakupan

- Ilustrasi hasil image generation untuk dekorasi (dibuang, prinsip 7).
- Menjalankan kode buatan LLM dan menerima SVG, Mermaid, TikZ, atau matplotlib bebas.
- Penilaian gambar oleh validator vision sebagai syarat lolos.
- Implementasi renderer dan penyajian di aplikasi (frontend belum dimulai); backend hanya menyediakan bentuk asli dan teks naratif.
- Mengubah aturan jenjang HOTS dan LOTS, atau level C6.

## Perubahan data

Diimplementasikan: migrasi `backend/migrations/versions/a7b1c9d4e2f0_add_stimulus_jenis_spesifikasi.py` (belum diterapkan ke DB mana pun dari sesi kerja; SQL `upgrade --sql` sudah ditinjau).

- `soal_stimulus.jenis` (Text, default `teks`).
- `soal_stimulus.spesifikasi` (JSONB, nullable): spesifikasi data jenis non-teks, termasuk `skema_versi` karena menjadi kontrak dengan frontend. Kolom `tabel`, `source_markup`, `readable_text`, `ringkasan` yang sudah ada tetap dipakai.
- Gambar tidak dibuat dan tidak disimpan di server. Sumber kebenaran adalah `spesifikasi`; frontend merender dari spesifikasi itu (keputusan 2026-11-02).

Kuis lama tidak dimigrasi (`jenis` teks).

## Perubahan API

Diimplementasikan: `QuestionStimulusResponse` (guru) dan `QuestionStimulusStudentResponse` (siswa) memuat `jenis` (default `teks`) dan `spesifikasi` (nullable) di samping `readable_text`, `tabel`, dan `ringkasan`; kompatibel mundur. Regenerasi stimulus (`POST /quizzer/teacher/soal/stimulus/regenerate/{soal_id}`) untuk stimulus bertipe mengedit spesifikasi lalu menurunkan ulang teks; bentuk permintaan tidak berubah. Edit spesifikasi langsung oleh guru belum ada. Sinkronisasi Postman dilakukan manual (konektor belum diotorisasi).

## Perubahan AI

- Prompt generator: bagian jenis stimulus yang aktif dan skemanya (hanya jenis yang dinyalakan, supaya prompt tidak membengkak), ditulis umum tanpa daftar contoh. `QUIZ_PROMPT_VERSION` naik saat implementasi; versi prompt Annoter tidak terpengaruh.
- Konfigurasi `QUIZ_STIMULUS_TYPES` (daftar jenis aktif); bawaan hanya `teks`. `QUIZ_MARKUP_ENABLED` tetap mengatur tabel dan rumus (Fase 1).
- Tidak ada panggilan LLM tambahan untuk penurunan teks dan render; biaya tambahan hanya token spesifikasi pada keluaran generator.
- Lapisan baru di `ai-services/quizzer/` (skema, pemeriksa, penurun teks per jenis) tetap komputasi murni; backend yang menyimpan.

## Aksesibilitas

TalkBack hanya membaca `readable_text` yang diturunkan dari spesifikasi. Data diberikan sebagai tabel linear lewat mekanisme ADR 0008 sehingga siswa dapat menelusuri sel demi sel. Soal tidak boleh bergantung pada tampilan visual saja. Nama titik dan bangun mengikuti aturan baca-lantang Quizzer. Pemeriksaan "semua angka spesifikasi ada di teks" menjaga kelengkapan. `a11y-reviewer` meninjau contoh teks turunan tiap jenis sebelum jenis itu dinyalakan. Uji dengar nyata dengan siswa atau guru SLB tetap diperlukan dan tidak dapat digantikan.

## Risiko per jenis

| Kelompok | Risiko | Mitigasi utama |
|---|---|---|
| teks, tabel, rumus, dokumen | rendah | sudah ada; gerbang `QUIZ_MARKUP_ENABLED` |
| grafik_data | rendah sampai sedang | pemeriksa jumlah dan kelas; teks berupa tabel data |
| bidang_koordinat, garis_bilangan | rendah sampai sedang | templat fungsi bernama; titik dan interval dalam JSON |
| diagram_relasi | sedang | jumlah peluang cabang, graf tanpa siklus, relasi himpunan dihitung kode |
| geometri_datar | tinggi | LLM tanpa koordinat; kode menghitung dan memeriksa konsistensi; mulai dari segitiga dan segiempat |
| bangun_ruang | tinggi | templat tetap; dikerjakan terakhir |
| campuran | mengikuti komponen | tiap komponen aman dulu |

## Pintu aktivasi per jenis

Sebuah jenis dinyalakan hanya bila seluruh daftar ini terpenuhi: skema dan batas ukuran (jumlah titik, kategori, simpul), pemeriksa kode dengan tes, penurun teks deterministik dengan tes, renderer bila ada, sampel soal nyata dicek manual terhadap spesifikasi, tinjauan `a11y-reviewer`, dan persetujuan user. Urutan yang disarankan: Fase 1, lalu `grafik_data`, `bidang_koordinat` dan `garis_bilangan`, `diagram_relasi`, `geometri_datar`, `bangun_ruang`, `campuran`.

## Keputusan dan pertanyaan terbuka

Keputusan (2026-11-02, dari diskusi user dan partner):

1. **Peninjau gambar.** Guru diasumsikan dapat melihat. Tampilan Quizzer menyajikan stimulus asli (rumus, tabel, grafik, diagram, geometri) bersama teks naratifnya; guru dapat melihat atau mendengarkan teks naratif. Pertanyaan "siapa meninjau bila guru tidak melihat" tidak dikerjakan di spec ini.
2. **Lokasi render: di klien (frontend), dari `spesifikasi`.** Backend dan ai-services tidak merender dan tidak menyimpan gambar. Alasan: penyajian adalah urusan frontend; render dari data mengikuti ukuran font, tema, dan mode tinggi kontras; tidak ada berkas gambar yang perlu disimpan, dibersihkan, dan diberi versi; teks naratif dan visual keduanya berasal dari spesifikasi yang sama. Konsekuensi: skema `spesifikasi` menjadi kontrak API dengan frontend dan perlu stabil serta berversi (`skema_versi`), dan frontend mengimplementasikan renderer per jenis. Renderer server (SVG dari templat tetap) dapat ditambahkan nanti sebagai cadangan tanpa mengubah kontrak data.
3. **Prioritas jenis.** Tidak ada prioritas dari sekolah mitra; urutan yang disarankan di bagian "Pintu aktivasi per jenis" dipakai.
4. **Batas elemen.** Tidak ada batas pedagogis. Hanya batas teknis yang longgar (anggaran token keluaran, ukuran muatan, dan perlindungan dari spesifikasi berukuran tidak wajar) yang dapat diatur lewat konfigurasi; angkanya ditetapkan saat implementasi per jenis. Pembacaan panjang dijelajahi frontend (mode telusur tabel sel demi sel, ADR 0008).

Masih terbuka:

5. Waktu dan penguji uji dengar nyata (siswa tunanetra atau guru SLB) belum diketahui. Selama belum ada, `QUIZ_MARKUP_ENABLED` tetap mati sehingga tabel dan rumus di Quizzer (Fase 1) belum dinyalakan, dan jenis non-teks tidak dinyalakan.

## Verifikasi

1. Tiap jenis: tes deterministik untuk skema, pemeriksa, penurun teks, dan (bila ada) renderer, termasuk kasus batas dan input tidak valid; tanpa panggilan LLM.
2. Aturan jenjang: tes bahwa C1 sampai C3 tanpa stimulus dan C4 dan C5 dengan stimulus tetap berlaku setelah penambahan jenis.
3. Keamanan: tes bahwa spesifikasi dengan elemen di luar skema, string berisi markup, atau jumlah elemen melebihi batas ditolak.
4. Sampel nyata per jenis: 10 sampai 20 soal dibuat dengan LLM (hanya atas instruksi user), tiap spesifikasi dicek manual terhadap teks dan gambar; ambang kesetiaan ditetapkan sebelum jenis dinyalakan.
5. Akurasi jawab buta dari teks turunan dibanding spesifikasi; selisihnya mengukur kerugian verbalisasi.
6. Lewat API dan worker: soal dengan stimulus non-teks tersimpan dengan `jenis`, `spesifikasi`, dan teks turunan; edit spesifikasi menurunkan ulang.
7. `a11y-reviewer` pada contoh teks turunan; uji dengar nyata oleh pengguna.

## Status implementasi (2026-11-02, direvisi)

Jenis stimulus final: `teks`, `tabel`, `gambar`, `campuran` (ADR 0012). Rancangan tujuh jenis data dengan solver dan narator per jenis diganti karena terlalu hardcode dan bias; cakupan tidak lagi dibatasi daftar bentuk yang saya pilih, karena LLM menulis SVG sendiri. Semua jenis aktif secara bawaan dan dipilih model per soal HOTS; `QUIZ_STIMULUS_TYPES` membatasi (`teks` saja untuk stimulus teks). LaTeX nyala bawaan. Prompt generator memuat definisi Bloom C1 sampai C5 dari tabel Vanderbilt University Center for Teaching.

Skema (versi 1):
- `tabel`: `{judul, kolom[], baris[][]}`; sel teks, rumus sebagai LaTeX di antara tanda dolar; teks bacaan, `tabel`, dan `ringkasan` diturunkan kode.
- `gambar`: LLM menulis `{svg}`; server menulis ulang SVG bersih berdaftar putih, merendernya ke PNG, dan mengisi `deskripsi` lewat deskriptor gambar bersama (prompt Annoter); `deskripsi` menjadi `readable_text`, dan angka label gambar yang tidak ada di deskripsi menjadi temuan review.
- `campuran`: `{komponen[]}` dari `teks`, `tabel`, `gambar` (paling banyak 12 komponen, tidak bersarang).

Kontrak render klien: `gambar` ditampilkan lewat `flutter_svg` (`SvgPicture.string`) dibungkus `ExcludeSemantics` dan satu `Semantics` berisi `readable_text`; `tabel` lewat widget tabel Flutter dengan `Semantics` per baris; rumus lewat `flutter_math_fork` dari `source_markup`. Keterbatasan yang diketahui: teks di dalam SVG tidak mengikuti skala font sistem dan tidak interaktif; semantics per elemen dan kontras warna ditunda sampai ada prototipe TalkBack. Belum: renderer klien, penanda audit kesetiaan deskripsi terhadap SVG, sampel soal nyata, uji dengar.

Batas teknis (`quizzer/config.py`): `STIMULUS_MAX_CHARS` 60000, `STIMULUS_MAX_SVG_CHARS` 30000, `SVG_MAX_ELEMENTS` 400, `STIMULUS_MAX_DEPTH` 12.
