# 0012. Stimulus bertipe: tabel dan gambar (SVG tulisan LLM), render di klien

- Status: diterima (direvisi 2026-11-02)
- Tanggal: 2026-11-02

## Konteks

Stimulus soal HOTS Quizzer semula hanya teks. Banyak soal wajar memakai data, grafik, diagram, atau bangun, sedangkan siswa tunanetra hanya mendengar `readable_text`. Rancangan pertama memakai tujuh jenis data bertipe dengan narator dan solver per jenis (sekitar 1.380 baris). User menilai itu terlalu hardcode dan bias ke daftar yang dipilih, dan menekankan bahwa LLM sudah menguasai matematika. Spec: [0007](../specs/0007-stimulus-hots-bertingkat.md).

## Keputusan

- Jenis stimulus yang dipilih LLM per soal HOTS (semua aktif bawaan; env `QUIZ_STIMULUS_TYPES` membatasi, `teks` saja untuk stimulus teks): `teks`, `tabel`, `gambar`, `campuran` (komponen berurutan dari teks, tabel, gambar; tidak boleh bersarang).
- `gambar`: LLM generator hanya menulis SVG; teks bacaannya dibuat sistem. Server merender SVG bersih menjadi PNG (`common/svg_raster`, resvg-py) lalu memanggil deskriptor gambar bersama (`common/image_describe` dengan prompt deskripsi Annoter di `common/image_prompts`, hasilnya dibersihkan `common/speakable`), di dalam pipeline sebelum validator buta dan audit membaca soal. Deskripsi disimpan di `spesifikasi.deskripsi` bersama `svg`, di-cache menurut hash SVG, dan dibuat ulang saat SVG direvisi. Kode tidak mengeksekusi apa pun: `quizzer/stimulus/gambar.py` mengurai SVG dengan `xml.etree` setelah menolak DOCTYPE, ENTITY, komentar, dan instruksi pemrosesan, memeriksa daftar putih elemen dan atribut (tanpa `style`, skrip, tautan, gambar luar, `url()` selain `url(#id)` lokal), `viewBox`, batas ukuran, jumlah elemen, dan kedalaman, lalu MENULIS ULANG SVG bersih dari pohon yang sudah diperiksa (bukan meneruskan teks mentah). Angka pada label di dalam gambar yang tidak ada di deskripsi, notasi mentah, dan bagian 'tidak terbaca' menjadi temuan yang menaikkan `review_priority`. Klien menampilkan SVG (`flutter_svg`) dan membacakan `readable_text`.
- `tabel`: `{judul, kolom, baris}`; sistem menurunkan bacaan lewat linearisasi tabel bersama (`common/math_text`, ADR 0008); sel boleh LaTeX di antara tanda dolar.
- LaTeX nyala bawaan (`QUIZ_MARKUP_ENABLED=0` mematikan): LLM menulis `$...$`, bacaan diturunkan lewat verbalizer bersama (`common/formula`), dan bentuk asli disimpan di `markup` dan `source_markup` seperti Annoter.
- Aturan jenjang tetap: C1 sampai C3 tanpa stimulus, C4 dan C5 wajib. Rujukan "gambar tadi" atau "tabel tadi" diizinkan hanya untuk stimulus bertipe; foto, ilustrasi, dan sketsa tetap dilarang.
- Data: `soal_stimulus.jenis` dan `soal_stimulus.spesifikasi` (JSONB, memuat `skema_versi`), migrasi `a7b1c9d4e2f0`. Untuk `gambar`, `spesifikasi` berisi `svg` dan `deskripsi`. Respons guru dan siswa memuat keduanya.
- Regenerasi: stimulus bertipe direvisi sebagai spesifikasi baru (`revise_stimulus_typed`, jenis tetap), divalidasi registry, lalu soal sekelompok di-recheck.

## Konsekuensi

- Kode folder `stimulus/` menyusut dari sekitar 1.380 ke sekitar 400 baris; tidak ada daftar bangun, solver, atau kalimat matematika yang menyetir model.
- Harga yang dibayar: teks bacaan `gambar` berasal dari model vision yang membaca gambar, bukan diturunkan kode dari data, jadi masih bisa keliru (evaluasi lama: juri gambar hanya sepakat sekitar 60 persen). Karena deskriptor terpisah dari generator, deskripsi mencerminkan apa yang benar-benar tergambar, bukan maksud generator. Penjagaan: pemeriksa angka label vs deskripsi dan notasi mentah, penanda audit validator, dan tinjauan guru yang melihat gambar bersama deskripsinya (guru diasumsikan dapat melihat). Biaya: satu panggilan vision per gambar (di-cache) dan satu dependensi baru (resvg-py).
- Koordinat dan bentuk dihitung LLM sehingga bisa tidak presisi (mis. sudut tidak siku); tidak ada pemeriksaan geometri.
- SVG tidak mengikuti ukuran font sistem dan tidak interaktif; teks siswa tunanetra tidak bergantung padanya. Semantics per elemen dan kontras warna perlu prototipe di klien.
- Alternatif yang ditolak: kode yang dijalankan (Dart tidak bisa dijalankan saat runtime; JS di WebView menambah risiko dan beban aksesibilitas), data per jenis dengan solver dan narator (terlalu hardcode dan bias), render server ke berkas gambar (berkas perlu disimpan dan diberi versi).
- Menyalakan jenis non-teks untuk siswa tetap menunggu renderer klien, tinjauan TalkBack, dan sampel soal nyata.

## Riwayat

Versi pertama (data bertipe: `grafik_data`, `garis_bilangan`, `bidang_koordinat`, `diagram_relasi`, `geometri_datar`, `bangun_ruang` dengan solver dan narator per jenis, `jenis_stimulus`, kontrak render `fl_chart` dan `CustomPainter`) diganti pada 2026-11-02 karena terlalu hardcode dan tidak pernah dipilih model pada uji (0 dari 36 soal HOTS). Riset pustaka Flutter yang menjadi dasar kontrak lama (fl_chart, CustomPainter, flutter_svg) masih berlaku untuk `flutter_svg`: satu `semanticsLabel` per gambar, teks tidak mengikuti skala font.

## Pembaruan: routing teks bacaan lewat modul bersama (2026-11-02)

Generator tidak lagi menulis teks bacaan untuk bentuk mentah apa pun. Routing: rumus (`$...$`) lewat `common/formula` dan `common/math_text`; tabel lewat linearisasi bersama `spoken_table`, `table_readable`, `table_summary` (jalur akhir yang sama dengan Annoter; MLLM Annoter untuk tabel tidak dipakai karena struktur tabel sudah ada); gambar lewat rasterisasi dan deskriptor gambar bersama. Bentuk mentah tetap disimpan seperti Annoter: LaTeX di `markup` dan `source_markup`, struktur tabel dan SVG di `spesifikasi`. Untuk mematuhi ADR 0004 (fitur hanya bergantung pada `common/`), prompt deskripsi gambar, `speakable`, dan `phrases` dipindahkan dari `annoter/` ke `common/` tanpa mengubah teks prompt Annoter (snapshot tes Annoter tetap hijau). Fonts: di Docker `fonts-liberation` (Dockerfile), di dev berkas `.ttf` bebas lisensi boleh ditaruh di `common/fonts/` bila font sistem tidak cukup; render pada Windows memakai font sistem.
