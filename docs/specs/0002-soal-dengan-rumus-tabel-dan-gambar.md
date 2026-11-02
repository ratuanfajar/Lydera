# 0002. Soal Quizzer dengan rumus LaTeX, tabel, dan gambar (tampilan visual dan teks siap-TalkBack)

- Status: Fase A selesai (2026-10-27); Fase B gambar ditahan
- Tanggal: 2026-10-27
- ADR terkait: -. Dasar: [spec 0001](0001-pipeline-quizzer-plan-then-generate.md), [ADR 0005](../adr/0005-format-prompt-dan-klasifikasi-gambar-annoter.md)

## Masalah

Soal Quizzer sekarang teks murni: rumus hanya berupa kata, tabel dan gambar tidak ada. Akibatnya:

1. Soal yang butuh rumus, tabel, grafik, atau geometri harus dinyatakan lengkap dengan kata (keterbatasan yang diterima di spec 0001), sehingga banyak topik matematika tidak bisa diujikan dengan wajar.
2. Siswa low vision dan guru yang melihat tidak punya tampilan visual rumus atau tabel soal, padahal Annoter sudah menyimpan keduanya (`source_markup` untuk tampilan, `readable_text` untuk TalkBack).

Terdampak: siswa tunanetra dan low vision, guru yang meninjau soal.

## Perilaku yang diharapkan

### Fase A: rumus LaTeX dan tabel

1. Generator menulis soal, opsi, langkah, kesimpulan, dan stimulus dengan LaTeX inline (`$...$`), serta tabel terstruktur (judul kolom dan baris) bila materi membutuhkannya. Gambar tetap di luar cakupan.
2. Setiap teks disimpan dalam dua bentuk, seperti blok teks Annoter: markup untuk tampilan visual UI dan `readable_text` yang diverbalisasi untuk TalkBack. Teks tanpa rumus atau tabel tidak berubah.
3. `readable_text` diturunkan dari markup: rumus lewat verbalizer yang sama dengan Annoter (few-shot, kesetiaan 97,1% pada rumus buku, belum diukur pada rumus buatan LLM); tabel dilinearisasi oleh kode dari struktur baris dan kolom (judul kolom disebut, lalu baris demi baris), tanpa LLM.
4. Validator menjawab buta dan mengaudit dari `readable_text`, yaitu teks yang didengar siswa. Bila verbalisasi salah, jawaban validator berbeda dan soal ditandai prioritas tinggi. Audit juga diberi markup dan ditanya apakah `readable_text` setia terhadapnya.
5. Pemeriksaan kode: sintaks LaTeX valid, tabel persegi (jumlah sel sama tiap baris), dan aturan baca-lantang spec 0001 berlaku pada `readable_text`, bukan pada markup.
6. Guru melihat tampilan visual dan teks siap-baca berdampingan saat meninjau. Edit manual markup oleh guru menurunkan ulang `readable_text`.
7. Temuan verifier tetap hanya menandai soal (spec 0001).

Catatan implementasi Fase A (2026-10-27): verbalizer rumus diganti gaya kelas dengan pemeriksa struktur ([ADR 0007](../adr/0007-verbalizer-rumus-gaya-kelas-dengan-pemeriksa-struktur.md)). Fitur dikendalikan saklar `QUIZ_MARKUP_ENABLED` (bawaan mati; mati berarti soal ditulis dengan kata tanpa LaTeX dan tabel) dan dinyalakan setelah uji dengar nyata dengan siswa atau guru SLB. Temuan pemeriksa bacaan dan rumus kompleks hanya menandai soal (`review_priority` tinggi), tanpa regenerasi otomatis.

### Fase B: gambar sebagai stimulus (DITAHAN; rencana fitur)

Belum dikerjakan. Dicatat sebagai rencana supaya keputusan dan batasannya tidak hilang.

- Gambar buatan LLM ditulis dalam format deklaratif (SVG statis atau JSON grafik/geometri yang dirender perender aman), bukan piksel. Model gambar raster tidak direkomendasikan (label dan geometri tidak eksak); ketersediaan deployment model gambar di Azure belum diperiksa.
- Gambar disimpan untuk tampilan UI; deskripsi TalkBack diturunkan dari markup gambar (teks, bukan piksel) seperti pola Annoter, lalu dicek konsistensinya oleh kode (semua titik dan label yang disebut ada di markup, koordinat wajar) dan validator.
- Kode buatan LLM tidak dijalankan; SVG disanitasi (tanpa skrip). Validator vision tidak jadi syarat lolos (juri gambar hanya sepakat sekitar 60%).
- Pengaman utama adalah guru melihat gambar dan deskripsi berdampingan; ini mengandalkan guru yang bisa melihat.
- Prasyarat: Fase A selesai, frontend mampu merender, dan sampel gambar dicek manual dengan ambang kesetiaan yang ditetapkan sebelum diaktifkan. Mulai dari grafik fungsi dan geometri lingkaran.
- Pertanyaan terbuka: siapa yang meninjau gambar bila guru tidak melihat; format deklaratif mana yang dirender frontend.

## Di luar cakupan

- Rendering LaTeX dan tabel di aplikasi (frontend belum dimulai); spec ini hanya menyiapkan data dan API.
- Gambar (Fase B) sampai diaktifkan.
- Mengubah Annoter; verbalizer dipindah tanpa mengubah perilakunya.

## Perubahan data

Migrasi Alembic (lewat `/alembic-migration`, persetujuan user, hanya DB dev dari sesi ini):

- `soal.markup` (JSONB, nullable): `{question, options: {A..D}, langkah: [...], kesimpulan}` berisi markup; null berarti sama dengan teks biasa. `soal_stimulus.source_markup` sudah ada dan dipakai untuk stimulus.
- Tabel soal disimpan sebagai HTML sederhana dalam markup yang sama.

Kuis lama tidak dimigrasi (markup null).

## Perubahan API

- Respons soal (guru dan hasil) memuat `markup` nullable di samping teks siap-baca; kompatibel mundur.
- Edit soal (PATCH) menerima `markup`; backend menurunkan ulang `readable_text`.
- Sinkronkan Postman lewat `/api-contract-sync`.

## Perubahan AI

- Verbalizer rumus dan prompt-nya dipindah dari `annoter/` ke `common/` (batas ADR 0004: fitur hanya bergantung pada `common/`); Annoter memakainya dari sana tanpa mengubah perilaku. Linearisasi tabel teks-saja ditambahkan di `common/`.
- Prompt generate Quizzer menulis LaTeX dan tabel terstruktur; `PROMPT_VERSION` naik bila prompt Annoter ikut berubah, selain itu `QUIZ_PROMPT_VERSION`.
- Biaya: satu panggilan verbalisasi per rumus (di-cache, paralel). Estimasi dan waktu diukur saat verifikasi.

## Aksesibilitas

TalkBack hanya membaca `readable_text`. Rumus yang salah diverbalisasi bisa mengubah makna, jadi validator memakai teks itu sebagai sumber, dan guru melihat keduanya berdampingan. Tampilan visual tidak boleh menjadi satu-satunya pembawa informasi.

## Verifikasi

1. Kesetiaan verbalizer pada rumus buatan LLM: sampel sekitar 50 rumus, tiga ulangan, cek manual terhadap LaTeX (bukan hanya juri LLM).
2. Akurasi jawab buta dari `readable_text` dibanding dari markup pada soal yang sama; selisihnya mengukur kerugian verbalisasi.
3. Linearisasi tabel: uji deterministik untuk tabel bersel kosong, header ganda, dan angka desimal.
4. Sintaks LaTeX tidak valid dan tabel tidak persegi terdeteksi kode dan memicu satu kali perbaikan.
5. Uji lewat API dan worker: kuis dengan rumus dan tabel tersimpan dengan markup dan `readable_text`; edit manual menurunkan ulang `readable_text`.
6. Agen `a11y-reviewer` pada sampel soal; pengukuran tidak dengan TalkBack di perangkat nyata kecuali disediakan.
