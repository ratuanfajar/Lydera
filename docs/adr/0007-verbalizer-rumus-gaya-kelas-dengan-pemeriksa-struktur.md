# 0007. Verbalizer rumus bergaya kelas dengan pemeriksa struktur

- Status: diterima
- Tanggal: 2026-10

## Konteks

Bacaan rumus untuk TalkBack dibuat LLM (`common/formula.py`, dipakai Annoter dan Quizzer). Prompt lama membaca simbol secara literal. Pada uji nyata muncul bacaan yang sulit didengar ("f buka kurung g buka kurung empat tutup kurung tutup kurung") dan bacaan yang kehilangan cakupan (pangkat `2^{3x + 1}`, nilai mutlak `|x - 4|`, akar bersarang). Riset ([0005](../research/0005-pembacaan-rumus-untuk-tunanetra.md)) mendukung ucapan gaya kelas dengan penutup struktur dan aturan konsisten, dan memperingatkan konsistensi LLM.

## Keputusan

- Prompt rumus memakai panduan gaya ala ClearSpeak dalam Bahasa Indonesia: "f dari g dari empat" untuk fungsi (kurung hanya untuk argumen majemuk), penutup "selesai akar", "selesai pecahan", "selesai pangkat" untuk struktur majemuk, tingkat kurung bersarang ("kurung kedua"), bacaan seragam untuk himpunan, interval, nilai mutlak, trigonometri, logaritma, limit, sigma, matriks, vektor, dan huruf geometri dipisah. Disertai 27 contoh few-shot.
- `common/formula_check.spoken_issues` memeriksa bacaan terhadap struktur LaTeX di kode: simbol atau angka tersisa, penutup kurang atau berlebih, kurung tidak seimbang atau beruntun, notasi fungsi sederhana yang masih memakai kurung. `convert_checked` mencoba ulang sekali dengan temuan sebagai koreksi.
- Rumus yang masih bermasalah ditandai: Annoter memberi `review_priority` tinggi; Quizzer membawa temuan sebagai catatan soal (tanpa regenerasi otomatis). Rumus kompleks (bersarang dalam atau panjang) di Quizzer juga ditandai.
- Rumus memakai versi cache sendiri (`FORMULA_PROMPT_VERSION`) supaya cache tabel dan gambar Annoter tidak terhapus.
- Saklar `QUIZ_MARKUP_ENABLED` (bawaan mati saat ADR ini ditulis; sejak 2026-11-02 bawaan nyala, lihat ADR 0012): soal berumus dengan LaTeX dan tabel hanya aktif bila dinyalakan; bawaannya Quizzer menulis soal dengan kata. Dinyalakan setelah uji dengar nyata.
- Set uji lintas kategori disimpan di `ai-services/common/eval/` (`formula_cases.json` 62 rumus, `formula_cases_heldout.json` 49 rumus).

## Hasil evaluasi (3 ulangan per rumus; `gpt-5.4-mini`; juri rekonstruksi `grok-4.3`)

| Ukuran | Prompt lama | Prompt baru |
|---|---|---|
| Bersih pemeriksa struktur, set utama (62 rumus) | 135/186 (73%) | 184/186 (99%) |
| Bersih pemeriksa struktur, set terpisah (49 rumus) | 110/147 (75%) | 142/147 (97%) |
| Rekonstruksi benar oleh pendengar tiruan, set utama | 54/62 | 59/62 |
| Rekonstruksi benar oleh pendengar tiruan, set terpisah | 42/49 | 45/49 |
| Rumus yang bacaannya konsisten antar ulangan | 41/62 dan 28/49 | 56/62 dan 39/49 |
| Kesalahan cakupan nyata pada rekonstruksi (pangkat, nilai mutlak, akar bersarang, kurung hilang), kedua set | 8 | 0 |

Batas hasil: pemeriksa struktur ditulis oleh pihak yang sama dengan aturan prompt (sebagian melingkar). Aturan dan contoh disusun setelah melihat kegagalan set utama dan sebagian kegagalan set terpisah, jadi angka set terpisah memihak. "Pendengar tiruan" adalah LLM, bukan manusia, dan juri membuat beberapa penilaian salah soal notasi dekoratif (garis atas, `cases`, `\text`). Uji dengar nyata belum dilakukan.

## Konsekuensi

- Bacaan rumus lebih konsisten dan lebih jarang kehilangan cakupan pada kasus uji, dengan panjang rata-rata sama (sekitar 13 kata); kasus notasi langka belum terukur.
- Menjalankan ulang Annoter pada bab yang sama menghitung ulang rumusnya (versi cache baru); bab yang sudah masuk DB tidak berubah sampai dihitung ulang.
- Satu panggilan LLM tambahan hanya bila pemeriksa menemukan masalah.
- Alternatif yang ditunda: mesin aturan deterministik (parser LaTeX ke ucapan), bila kegagalan masih tinggi pada uji dengar atau notasi lain.

## Pembaruan 2026-11-02: aturan kondisional untuk titik berkoordinat dan plus-minus

Latar: bacaan Clarifier (spec 0006) menampilkan "C dari buka kurung h koma k tutup kurung" (terdengar seperti fungsi), "koma" antar koordinat yang bentrok dengan koma desimal, dan plus-minus yang terbaca "tambah kurang". Aturan ditambahkan sebagai prompt tambahan yang hanya dipakai bila LaTeX memuat titik bernama (huruf kapital diikuti dua atau tiga koordinat), pasangan koordinat utuh, himpunan pasangan, atau `\pm`/`\mp`. Rumus lain memakai prompt lama tanpa perubahan, sehingga `FORMULA_PROMPT_VERSION` tetap "2", cache Annoter dan Quizzer tetap berlaku, dan kunci cache prompt tambahan diberi akhiran `k`. Cek struktur baru: titik bernama harus memuat "koordinat", plus-minus harus dibaca "plus atau minus" dan minus-plus "minus atau plus". Rumus satu huruf, satu angka, dan satu huruf Yunani dibaca langsung tanpa LLM.

Evaluasi (3 ulangan, juri `grok-4.3`, 130 rumus: 62 lama, 49 heldout, 19 baru): dengan aturan untuk semua rumus, set heldout menurun (juri setia 130 dari 147, lama 134; ambigu 13 dari 147, lama 8; cek kode bermasalah 4, lama 1). Sebagian selisih itu derau juri (bacaan identik dinilai berbeda pada 10 dari 73 pasangan), tetapi tiga rumus berubah nyata: `\sqrt{\sqrt{t}+1}` mendapat "selesai akar" berlebih pada 3 dari 3 ulangan, `\log(ab)` kehilangan "kali", dan kurung bersarang tiga tingkat bergeser. Karena itu aturan dijadikan kondisional. Hasil kondisional pada 15 rumus yang terpicu: cek kode bermasalah 0 dari 42 (lama 33), bacaan sesuai harapan 42 dari 42 (lama 0), juri ambigu 2 (lama 13). Pada set lama dan heldout hanya satu rumus (rumus abc dengan plus-minus) yang terpicu; sisanya memakai prompt yang sama dengan sebelumnya.

Batas: kasus koordinat ditulis penulis sebelum dijalankan tetapi harapannya mengikuti aturan baru, jadi angka perbaikan memihak; ambang pemicu (regex) disetel pada notasi Kemendikdasmen dan bisa meleset pada notasi lain; belum ada uji dengar; perubahan ini belum ditinjau reviewer.

## Pembaruan 2026-11-02 (setelah review): pemicu dan evaluasi ulang

Review kode dan aksesibilitas menemukan pemicu terlalu longgar (`C(5, 2) = 10`, `F(x, y)`, distribusi, interval ber-tak-hingga terbaca sebagai titik) dan terlalu sempit (aksen, argumen bersuku, titik koma, himpunan dengan syarat, `±`). Pemicu kini mengecualikan titik yang diikuti `=` atau didahului `\sim`/`\mid`, mengecualikan rumus ber-`\infty`, dan menerima argumen bersuku, aksen, titik koma, serta himpunan dengan syarat. Prompt koordinat ditambah aturan koordinat bersuku banyak ("koordinat pertama ... dan koordinat kedua ..."), aturan koma desimal dan titik koma, serta contoh himpunan dengan syarat; kunci cache menjadi akhiran `k3`. Jalur regenerate Annoter memakai prompt koordinat bila rumusnya memicu, `readable_texts` membuang "titik" ganda, dan ejaan Yunani (termasuk ksi, kapa, kai dan huruf kapital) berlaku di teks polos.

Evaluasi ulang 3 ulangan, juri `grok-4.3`, 20 rumus terpicu (57 bacaan): bacaan sesuai harapan 57 dari 57 (prompt lama 0), cek kode bermasalah 0 (lama 45), ambigu menurut juri 4 (lama 17). Tanda juri yang tersisa: `x sub satu` (konvensi 'sub' prompt dasar) dan `M(1,5; 2)` (bacaan benar, dinilai ambigu), dianggap derau atau gaya. Batas yang tetap: `C(10, 3)` tanpa `=` masih terbaca titik; interval `x \in (2, 5)` memakai prompt dasar yang belum mendefinisikan `(a, b)` dan `[a, b]` (mengubahnya berarti menaikkan `FORMULA_PROMPT_VERSION`); belum ada uji dengar.
