# 0003. Tabel dengan dua mode baca: telusur sel dan ringkasan

- Status: disetujui
- Tanggal: 2026-10-27
- ADR terkait: [0008](../adr/0008-tabel-dua-mode-baca.md)

## Masalah

Tabel sekarang sampai ke siswa tunanetra hanya sebagai satu bacaan linear panjang ("Baris 1, ..., Baris 2, ..."). Siswa tidak bisa memilih untuk menelusuri tabel sel demi sel, dan tidak ada gambaran singkat tentang isi tabel sebelum bacaan panjang dimulai. Pada tabel besar siswa harus mendengarkan semuanya untuk tahu tabel itu tentang apa. Hal yang sama berlaku untuk tabel pada stimulus soal Quizzer.

## Perilaku yang diharapkan

Setiap tabel (blok `table` Annoter dan tabel pada stimulus Quizzer) dikirim ke klien dalam tiga bentuk sekaligus. Klien yang memilih bentuk mana yang ditampilkan atau dibacakan.

1. **Bacaan linear** (`readable_text`): tidak berubah, tetap menjadi cadangan.
2. **Mode telusur** (`tabel`): `{judul, kolom, baris}` sebagai data terstruktur supaya klien dapat membuat tabel yang bisa ditelusuri sel demi sel.
3. **Mode ringkasan** (`ringkasan`): satu sampai dua kalimat yang dibacakan sebagai teks tak terlihat di atas tabel.

Aturan per sumber:

- **`tabel` adalah bentuk yang dibacakan.** Sel sudah diverbalisasi: rumus `$...$` menjadi kata, huruf Yunani dieja (alfa, teta), sel kosong menjadi "kosong", nama kolom tidak kosong dan unik ("Kolom 2", "Nilai (kolom 1)"). Klien memakainya langsung sebagai label pembaca layar. Tampilan visual memakai `source_markup` (HTML), yang bukan untuk dibacakan.
- **Annoter**: model penglihatan membaca gambar tabel dan menghasilkan tabel terstruktur yang sudah dikoreksi dari kesalahan OCR (sel gabungan diulang, judul bertingkat digabung, ekspresi matematika di sel ditulis `$...$`) dan satu kalimat topik. Bacaan linear dan ringkasan disusun oleh kode dari tabel itu, sehingga isinya selalu sama dengan sel. Ringkasan = kalimat topik + jumlah kolom dan baris data + nama kolom (maksimal enam, sisanya "dan N kolom lainnya"); tanpa nilai sel dan tanpa tafsir tren.
- **Quizzer**: `tabel`, ringkasan, dan bacaan linear dibuat kode dari tabel terstruktur pada stimulus. Ringkasan memuat judul, jumlah kolom dan baris data, serta nama kolom; tanpa LLM supaya tidak membocorkan jawaban. Batas desain: soal yang menanyakan jumlah kolom atau baris terjawab oleh ringkasan.
- Format bacaan linear: "Tabel Nilai Siswa. Ada 3 kolom: Nama, Nilai UTS, dan Nilai UAS. Baris 1. Nama: Ani; Nilai UTS: 80; Nilai UAS: 85." (titik dua dan titik koma memisahkan nama kolom, nilai, dan pasangan).
- Guru dapat memperbaiki ringkasan, bacaan, dan `tabel` blok Annoter lewat regenerasi dengan feedback; ketiganya dihasilkan ulang bersama dan `review_priority` menjadi `high` bila pemeriksa kode menemukan masalah. Pada Quizzer, stimulus ditampilkan ke guru dengan `source_markup` (mentah) dan `readable_text`; ringkasan dan `tabel` ikut berubah saat stimulus direvisi.
- Tabel yang strukturnya tidak valid (jumlah sel baris tidak sama dengan jumlah kolom, topik bermarkdown, LaTeX sel rusak, ukuran berbeda dari OCR) membuat blok berprioritas tinjauan `high`. Bila struktur tidak valid, `tabel` bernilai `null` dan bacaan linear memakai bacaan dari model; klien memakai bacaan linear.
- Data lama tanpa `ringkasan` dan `tabel` tetap valid: klien menganggap keduanya boleh kosong dan memakai bacaan linear.

## Di luar cakupan

- UI Flutter (belum dimulai). Kontrak di bawah ini yang dikunci; cara menampilkan dan dukungan semantik tabel di TalkBack perlu prototipe di perangkat nyata.
- Mengisi ulang tabel yang sudah ada di database (menulis ke DB dan memanggil LLM; perlu persetujuan terpisah).
- Edit manual sel tabel Annoter oleh guru (hanya lewat regenerasi dengan feedback).
- Pilihan mode per siswa (preferensi disimpan di klien).

## Perubahan data

Migrasi baru (satu revisi):

- `blocks.ringkasan` Text nullable.
- `blocks.tabel` JSONB nullable.
- `soal_stimulus.ringkasan` Text nullable.
- `soal_stimulus.tabel` JSONB nullable.

Kolom JSONB memakai `none_as_null` supaya baris tanpa tabel berisi SQL NULL, bukan JSON `null`.

## Perubahan API

Tidak ada endpoint baru. Field baru yang boleh `null` pada respons yang sudah ada:

- Blok (`BlockResponse`, `BlockPreviewResponse`, `RegenerateDetailResponse`): `ringkasan`, `tabel`.
- Stimulus soal untuk guru dan siswa: `ringkasan`, `tabel`.
- `StimulusCreateRequest`: `ringkasan` opsional.

Kontrak untuk klien:

- Bila mode telusur dipakai, bacaan linear disembunyikan dari pembaca layar, dan sebaliknya, supaya tabel tidak terbaca dua kali. Ringkasan dan bacaan linear tidak dibacakan berurutan karena keduanya menyebut judul dan nama kolom.
- Label tiap sel disusun klien dari `kolom` dan `baris`: bila kolom pertama berisi teks (bukan angka), pakai sebagai kepala baris, mis. "Ani, Nilai UTS: 80, baris 1 dari 3"; selain itu "Nilai UTS, baris 1 dari 3: 80". Sel kosong sudah berisi "kosong".
- `source_markup` stimulus hanya untuk tampilan visual, jangan dibacakan.
- Bacaan linear tabel besar adalah satu teks panjang; klien sebaiknya memecahnya di awal setiap "Baris N.".

Koleksi Postman disinkronkan lewat `api-contract-sync`.

## Perubahan AI

- Prompt tabel Annoter: keluaran JSON menambah `baris` pada `pengamatan` dan field `topik`; aturan sel gabungan, judul bertingkat, LaTeX di sel, dan topik. `TABLE_PROMPT_VERSION` baru di `common/config.py` (mengikuti `FORMULA_PROMPT_VERSION`) supaya cache gambar dan rumus tidak terhapus; `PROMPT_VERSION` tetap karena prompt gambar tidak berubah.
- Biaya: satu panggilan penglihatan per tabel seperti sebelumnya, dengan keluaran sedikit lebih panjang karena memuat seluruh sel.
- Quizzer: tanpa panggilan LLM tambahan.
- Model juga menulis `deskripsi` (bacaan cadangan) yang dibuang bila struktur valid; biayanya token keluaran tambahan.

## Aksesibilitas

- Mode ringkasan memberi gambaran sebelum siswa memutuskan menelusuri atau membaca linear.
- Huruf Yunani, rumus, dan sel kosong sudah dibacakan dengan kata di `tabel`, jadi TalkBack tidak membaca LaTeX atau simbol mentah.
- Mode telusur memberi kendali penuh pada siswa atas urutan baca sel.
- Ringkasan memakai teks biasa tanpa markdown dan tanpa kalimat pembuka.

## Verifikasi

- Evaluasi prompt tabel pada sampel tabel dengan kebenaran dasar (tiga ulangan): kecocokan sel, jumlah kolom dan baris, kepatuhan aturan ringkasan, konsistensi bacaan linear dengan sel.
- Uji unit untuk ringkasan deterministik dan validasi struktur.
- Migrasi pada database dev, lalu alur nyata: unggah ingest `annotated.json` berisi tabel, baca blok, regenerasi blok tabel, buat kuis dengan stimulus bertabel (saklar markup nyala) dan periksa `ringkasan` dan `tabel` pada respons guru dan siswa.
- Sinkronisasi Postman dan baca ulang koleksi.
