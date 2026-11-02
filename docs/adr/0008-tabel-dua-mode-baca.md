# 0008. Tabel dengan dua mode baca: telusur sel dan ringkasan

- Status: diterima
- Tanggal: 2026-10

## Konteks

Tabel (blok `table` Annoter dan tabel pada stimulus Quizzer) sampai ke siswa tunanetra sebagai satu bacaan linear. Siswa tidak bisa menelusuri sel demi sel dan tidak mendapat gambaran singkat isi tabel sebelum bacaan panjang. Spec: [0003](../specs/0003-tabel-dua-mode-baca.md).

Uji awal prompt tabel dengan satu field tambahan (`ringkasan`) menunjukkan risiko: pada sebagian ulangan model mengisi bacaan linear dengan ringkasan dan tidak membaca baris sama sekali (bacaan tidak memuat sel tabel pada 5 dari 27 ulangan sebelum prompt diperjelas). Selain itu HTML OCR dari MinerU tidak memiliki baris judul (`<th>`), jadi tidak bisa dipakai langsung sebagai tabel terstruktur.

## Keputusan

- Setiap tabel dikirim dalam tiga bentuk: bacaan linear (`readable_text`), `tabel` terstruktur `{judul, kolom, baris}` untuk mode telusur, dan `ringkasan` untuk mode ringkasan. Klien memilih bentuk yang ditampilkan.
- `tabel` adalah bentuk yang dibacakan (`math_text.spoken_table`): rumus diverbalisasi, huruf Yunani dieja, sel kosong "kosong", nama kolom tidak kosong dan unik. Tampilan visual memakai `source_markup`.
- Annoter: satu panggilan penglihatan menghasilkan tabel terstruktur (sel dikoreksi dari gambar, sel gabungan diulang, judul bertingkat digabung, ekspresi matematika di sel ditulis `$...$`) dan satu kalimat topik. Bacaan linear dan ringkasan disusun oleh kode dari tabel itu, bukan oleh LLM, sehingga bacaan, ringkasan, dan sel selalu sama dan tidak ada sel yang terlewat. Bacaan dari LLM (`deskripsi`) hanya cadangan bila struktur tidak valid, dan blok itu diberi prioritas tinjauan `high`.
- Quizzer: ringkasan dan `tabel` dibuat kode dari tabel stimulus (`table_summary`, `spoken_table`), bukan LLM, supaya tidak membocorkan jawaban atau menambah klaim.
- Ringkasan hanya menyebut topik (Annoter) atau judul (Quizzer), jumlah kolom dan baris data, dan nama kolom, tanpa nilai sel dan tanpa tafsir tren. Jumlah dan nama kolom selalu dari kode, jadi tidak bisa berbeda dari tabel. Pemeriksa kode menandai topik bermarkdown atau panjang, LaTeX sel yang rusak, dan ukuran tabel yang berbeda dari hasil OCR.
- Format bacaan linear memakai titik dua dan titik koma ("Baris 1. Nama: Ani; Nilai UTS: 80.") supaya nama kolom, nilai, dan pasangan tidak ambigu bila nama berakhir atau nilai diawali angka.
- Data: `blocks.ringkasan`, `blocks.tabel` (JSONB), `soal_stimulus.ringkasan`, `soal_stimulus.tabel` (JSONB); semuanya boleh kosong untuk data lama.
- Versi cache tabel sendiri (`TABLE_PROMPT_VERSION`, kini 4), mengikuti preseden `FORMULA_PROMPT_VERSION` ([0007](0007-verbalizer-rumus-gaya-kelas-dengan-pemeriksa-struktur.md)), supaya cache gambar tidak terhapus. `PROMPT_VERSION` tidak naik karena prompt gambar tidak berubah.

## Hasil evaluasi (3 ulangan per tabel; `gpt-5.4-mini`; 9 tabel sintetik dengan kebenaran dasar)

Tabel dirender sebagai gambar bersih dengan HTML OCR yang sengaja diberi satu angka salah pada dua tabel, dan mencakup judul, desimal koma, angka negatif, huruf Yunani, sel kosong, tanpa baris judul, tabel 10 baris, dan judul bertingkat.

| Ukuran | Hasil |
|---|---|
| Kecocokan sel dan ukuran tabel terhadap kebenaran dasar | 9 dari 9 tabel cocok sempurna di 3 dari 3 ulangan (27 dari 27), setelah ejaan Yunani dan "kosong" disamakan |
| Angka OCR yang salah dikoreksi dari gambar | 2 dari 2 tabel, di semua ulangan |
| Judul bertingkat (UTS dan UAS di bawah Nilai) | digabung menjadi "Nilai UTS", "Nilai UAS" di 3 dari 3 ulangan setelah aturan ditambahkan (sebelumnya 1 dari 3 ulangan salah menaruh sub-judul di baris data) |
| Ringkasan tanpa nilai sel | semua ulangan (ringkasan kini disusun kode dari topik model dan struktur tabel) |

Batas hasil: gambar sintetik bersih, bukan tabel buku yang dipindai; sampel kecil; sebagian aturan ditambahkan setelah melihat kegagalan putaran pertama (bacaan linear yang tidak memuat sel pada 5 dari 27 ulangan, sub-judul masuk baris data), jadi angka putaran terakhir memihak. Ejaan huruf Yunani dalam topik model masih bisa berbeda (alfa dan alpha); sel dinormalkan oleh kode. Belum ada uji dengar dengan siswa.

## Konsekuensi

- Klien (Flutter, belum dimulai) harus menyembunyikan bacaan linear dari pembaca layar saat mode telusur aktif, dan menyusun label sel dari `kolom` dan `baris`. Dukungan semantik tabel TalkBack di Flutter perlu prototipe di perangkat nyata.
- Bacaan linear tabel Annoter kini berformat seragam dengan tabel Quizzer ("Baris 1: kolom nilai, ...") dan tidak lagi bervariasi menurut gaya model.
- Tabel yang sudah ada di DB tidak punya `ringkasan` dan `tabel` sampai dihitung ulang; klien memakai bacaan linear.
- Alternatif yang ditunda: ringkasan Annoter oleh LLM yang menjelaskan tren (ditolak karena risiko tafsir salah), mode telusur dari HTML OCR langsung (ditolak karena tanpa baris judul dan tanpa koreksi OCR).
