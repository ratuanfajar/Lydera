# 0001. Filter sumber web Clarifier: allowlist domain atau pola wildcard

- Tanggal: 2026-10-27
- Status: selesai (input untuk Fase 6; rekomendasi final di Pembaruan 3)
- Keyakinan: sedang (uji kecil: 12 panggilan Tavily basic, dua pertanyaan)

## Pertanyaan

Bisakah kredibilitas sumber web Clarifier dijaga dengan pola wildcard (mis. `*.edu`) alih-alih daftar domain eksplisit, tanpa tier?

## Konteks Lydera

Clarifier hanya boleh mengutip sumber yang kredibel untuk siswa tunanetra SMA. Saat ini ada `search_oer` (daftar domain) dan `search_academic_web` (seluruh web + label tier); tier 3 meloloskan sumber seperti bucket S3 dan blog (F-014).

## Temuan

- Dokumentasi Tavily: `include_domains` maksimal 300 domain; hanya domain dan subdomain polos; wildcard, regex, dan URL berpath tidak didukung; mode bawaan `restrict` adalah filter keras; domain induk mencakup semua subdomainnya. Sumber: docs.tavily.com (endpoint search, changelog Agustus 2026), diakses 2026-10-27.
- Uji empiris `include_domains`: `["edu"]` dan `["*.edu"]` menghasilkan HTTP 400; `[".edu"]` menghasilkan 0 hasil tanpa error; `["ac.id"]` berhasil (20 hasil, semua subdomain `ac.id`); `["go.id"]` menghasilkan 0 hasil pada dua kueri.
- Uji saring-sesudah-pencarian (tanpa filter, lalu dicocokkan sufiks `.edu/.ac.id/.go.id/.gov`): 0 dari 19 hasil lolos (kueri Inggris), 1 dari 20 (kueri Indonesia). Hasil mentah didominasi Wikipedia, Scribd, YouTube, blog.
- Isi hasil `ac.id`: hampir seluruhnya skripsi, jurnal, dan repositori (`skripsi full.pdf`, `lampiran.pdf`), bukan materi ajar SMA.
- Isi hasil `rumahbelajar.id + belajar.id`: PDF perangkat ajar Kemendikbud (`static.perangkat-ajar.belajar.id`), termasuk berkas unggahan guru (`USR.*.pdf`) selain berkas resmi (`SMA.E.MAT.ARF.1.pdf`).
- Isi hasil `khanacademy.org + openstax.org + oercommons.org + mit.edu`: 20 hasil relevan, didominasi Khan Academy (geometri lingkaran, sudut keliling).

## Inferensi

- Kredibilitas domain tidak sama dengan kualitas isi: `ac.id` kredibel tetapi tidak relevan sebagai materi ajar; `belajar.id` bercampur antara resmi dan unggahan pengguna.
- Wildcard berbasis TLD tidak bisa ditegakkan di sisi API dan hasil saring-sesudah nyaris selalu kosong, jadi tidak layak sebagai mekanisme utama.

## Opsi

| Opsi | Kualitas | Risiko | Catatan |
|---|---|---|---|
| Wildcard TLD (`*.edu`) | rendah | tinggi (400 atau kosong) | tidak didukung Tavily |
| Saring sufiks sesudah pencarian | rendah | hasil kosong | 0-5% lolos |
| Sufiks multi-label sebagai domain (`ac.id`) | sedang | isi tidak relevan, tidak konsisten (`go.id` kosong) | perlu uji per sufiks |
| Daftar datar domain eksplisit, tanpa tier | tinggi | pemeliharaan daftar | subdomain otomatis tercakup |

## Rekomendasi

Satu daftar datar domain eksplisit (tanpa tier), ditegakkan dua lapis: `include_domains` mode `restrict` dan pemeriksaan host di kode. Awal: `khanacademy.org`, `openstax.org`, `oercommons.org`, `mit.edu`, `rumahbelajar.id`, `belajar.id`, `kemendikdasmen.go.id`, `kemdikbud.go.id`; putuskan apakah `static.perangkat-ajar.belajar.id` dikecualikan (`exclude_domains`) karena memuat unggahan guru. Sufiks seperti `ac.id` hanya ditambah bila diuji relevan.

## Pembaruan: subdomain yang muncul per domain (uji 8 panggilan basic, kueri materi lingkaran)

| Domain di daftar | Subdomain yang muncul (jumlah hasil) | Penilaian |
|---|---|---|
| khanacademy.org | khanacademy.org (19), en.khanacademy.org (1) | relevan |
| openstax.org | openstax.org (19), assets.openstax.org (1) | relevan |
| oercommons.org | oercommons.org (16), goopennc.oercommons.org (3), backup.oercommons.org (1) | relevan (portal NC dan cadangan) |
| mit.edu | direct.mit.edu (5, jurnal MIT Press), help.wi.mit.edu (4), web.mit.edu, mirrors, tilingsearch, esp, groups.csail, people.csail, dspace, math (masing-masing 1-2) | terlalu lebar, banyak bukan materi ajar; pakai `ocw.mit.edu` saja |
| rumahbelajar.id | rumahbelajar.id (13) | relevan |
| belajar.id | static.perangkat-ajar.belajar.id (20) | hanya PDF perangkat ajar; campuran resmi dan unggahan guru |
| kemendikdasmen.go.id | murid.kemendikdasmen.go.id (13), repositori.kemendikdasmen.go.id (5), sma.kemendikdasmen.go.id (1), pusmendik.kemendikdasmen.go.id (1) | `murid.` dan `sma.` relevan; `repositori.` berisi dokumen/modul guru; `pusmendik.` asesmen |
| kemdikbud.go.id | download.garuda.kemdikbud.go.id (18), sbh.bppp.kemdikbud.go.id (1) | `garuda` adalah portal jurnal, tidak relevan |

Kesimpulan: domain induk yang luas (`mit.edu`, `kemdikbud.go.id`) menarik banyak subdomain yang bukan materi ajar. Mendaftarkan subdomain tertentu hanya mencocokkan host persis itu, jadi daftar sebaiknya memakai subdomain yang dipilih untuk domain luas dan domain induk untuk domain yang isinya seragam.

Daftar usulan yang diperbarui: `khanacademy.org`, `openstax.org`, `oercommons.org`, `ocw.mit.edu`, `rumahbelajar.id`, `belajar.kemdikbud.go.id`, `murid.kemendikdasmen.go.id`, `buku.kemendikdasmen.go.id`, `sma.kemendikdasmen.go.id`, `static.perangkat-ajar.belajar.id` (opsional, lihat keputusan unggahan guru). Tanpa `mit.edu`, `kemdikbud.go.id`, dan `kemendikdasmen.go.id` sebagai domain induk.

## Pembaruan 2: apakah filter berbasis TLD (`.org`, `.edu`, `.go.id`) berguna sebagai pelengkap daftar

Uji hibrida (4 kueri materi lingkaran, 4 panggilan basic): `include_domains` = daftar usulan dengan `include_domains_mode="prefer"`, lalu hasil di luar daftar diterima bila sufiksnya `.edu/.ac.id/.go.id/.gov/.sch.id/.edu.au/.ac.uk`.

- Dari 73 hasil, 37 berasal dari daftar. Sufiks menambah hanya 2: `jurnal.radenfatah.ac.id` (jurnal) dan `sman1cisarua.sch.id` (situs sekolah). Tidak ada tambahan `.edu` atau `.go.id`.
- Sufiks `.org` meloloskan `en.wikipedia.org`, `geeksforgeeks.org`, `dictionary.cambridge.org`, `snexplores.org` selain `khanacademy.org` dan `openstax.org`; `.org` bukan sinyal kredibilitas.
- Mode `prefer` mengembalikan campuran, sehingga jumlah hasil valid lebih sedikit dibanding `restrict` (yang seluruh 20 hasilnya berasal dari daftar).

Kesimpulan: sufiks TLD sebagai tambahan menambah sedikit hasil dengan kualitas rendah; tidak dipakai. Keputusan: `restrict` + daftar datar.

## Pembaruan 3: validasi cakupan, 12 kueri materi SMA (8 Indonesia, 4 Inggris)

Pengaturan: `include_domains` = 10 domain usulan, mode `restrict`, `search_depth=advanced`, `max_results=5`, 12 panggilan (sekitar 24 kredit). Penilaian relevansi saya baca dari judul dan skor Tavily; isi halaman belum dibaca.

- 12 dari 12 kueri menghasilkan hasil. Kueri Indonesia didominasi `murid.kemendikdasmen.go.id` (Ruang Murid) dengan judul tepat sasaran dan skor 0,6-0,9 (fungsi invers, komposisi fungsi, sudut pusat dan keliling, persamaan lingkaran, barisan aritmetika, aturan sinus-cosinus, peluang saling lepas). Kueri Inggris didominasi `khanacademy.org` dan `openstax.org` dengan skor 0,7-0,9.
- Domain yang tidak pernah muncul di 12 kueri: `oercommons.org`, `ocw.mit.edu`, `belajar.kemdikbud.go.id`, `buku.kemendikdasmen.go.id`, `sma.kemendikdasmen.go.id`.
- Sumber berisik: `static.perangkat-ajar.belajar.id` (dokumen alur tujuan pembelajaran dan modul ajar SD/unggahan guru), `rumahbelajar.id` (judul tidak terkait, mis. "Gemar Matematika 5", "FISIKA untuk SMA/MA Kelas X", skor 0,44-0,56), dan subdomain bahasa Khan Academy (`zh.khanacademy.org` untuk kueri Indonesia, `cs.khanacademy.org`).
- Kueri "notasi sigma dan induksi matematika" tidak punya halaman `murid.`; hasilnya turun ke artikel Khan (skor 0,52-0,55) dan sampah (skor 0,16-0,27). Skor di bawah sekitar 0,4 hampir selalu tidak relevan.

Rekomendasi tervalidasi:
- Daftar datar minimal: `murid.kemendikdasmen.go.id`, `openstax.org`, dan Khan Academy dengan host persis `www.khanacademy.org`, `id.khanacademy.org`, `en.khanacademy.org` (menyebut subdomain hanya mencocokkan host itu, sehingga `zh.` dan `cs.` tersingkir).
- Tidak dimasukkan dulu (tanpa bukti manfaat): `static.perangkat-ajar.belajar.id`, `rumahbelajar.id`, `oercommons.org`, `ocw.mit.edu`, `buku.`/`sma.`/`belajar.kemdikbud.go.id`. Ditambah bila uji topik lain menunjukkan celah.
- Ambang skor relevansi 0,7 (keputusan user); bila tidak ada hasil di atas ambang, tool mengembalikan "tidak ada di sumber tepercaya" dan model diminta mengatakannya.
- Tanpa tier, tanpa Wolfram, tanpa `search_academic_web`.

Belum diverifikasi: isi halaman `murid.` (banyak berupa Lab Maya/interaktif dan video; belum diperiksa apakah teksnya cukup untuk pembaca layar); cakupan topik di luar 12 kueri; perilaku host persis `www.khanacademy.org`.

## Pembaruan 4: kandidat tambahan (12 kueri yang sama + topik induksi, hanya domain kandidat, 10 hasil per kueri)

| Host | Hasil | Skor rata-rata / maks | Catatan |
|---|---|---|---|
| repositori.kemendikdasmen.go.id | 70 | 0,62 / 0,88 | modul resmi Kemendikdasmen (mis. "Modul SMA KK B"), PDF, berorientasi guru dan bisa berasal dari kurikulum lama (2016) |
| math.libretexts.org | 23 | 0,76 / 0,87 | OER universitas, mencakup fungsi invers, induksi, sigma |
| flexbooks.ck12.org + ck12.org | 9 | 0,82 / 0,88 | OER K-12, "Arc of a Circle", sudut tertulis |
| sma.kemendikdasmen.go.id | 2 | 0,66 / 0,75 | "Fungsi Invers Interaktif", resmi tetapi sedikit |
| ocw.mit.edu | 2 | 0,70 / 0,73 | kuliah induksi tingkat universitas |
| ocw.ui.ac.id | 1 | 0,87 / 0,87 | OCW UI, sistem koordinat Kartesius |
| mathworld.wolfram.com | 1 | 0,85 / 0,85 | rujukan ahli, ensiklopedis |
| geogebra.org (+ cdn) | 9 | 0,74 / 0,87 | materi unggahan pengguna, kredibilitas campuran |
| mathsisfun.com | 2 | 0,77 / 0,81 | edukatif tetapi komersial, bukan institusi |
| pusmendik.kemendikdasmen.go.id | 1 | 0,24 / 0,24 | tidak relevan |
| oercommons.org, nrich.maths.org, buku.kemendikdasmen.go.id, belajar.kemdikbud.go.id, ocw.itb.ac.id | 0 | - | tidak muncul |

Usulan tambahan: wajib `repositori.kemendikdasmen.go.id` (menutup celah Indonesia terbesar), `flexbooks.ck12.org`, `math.libretexts.org`; kecil tetapi aman `sma.kemendikdasmen.go.id`; opsional `ocw.mit.edu`, `ocw.ui.ac.id`, `mathworld.wolfram.com`. Tidak: `geogebra.org` (unggahan pengguna), `mathsisfun.com`, `pusmendik`.

Risiko: modul `repositori.` bisa berbeda kurikulum dan notasi dari buku Kurikulum Merdeka yang diunggah (Kelas X/XI 2021); skor relatif terhadap himpunan kandidat saja; isi PDF belum dibaca.

## Pembaruan 5 (koreksi): wildcard dan path pada `include_domains`

Halaman Best Practices Tavily (by domain) memuat contoh `["*.com"]`, `["linkedin.com/in"]`, dan pesan error API menyebut format valid: `example.com`, `api.example.com`, `*.example.com`, `example.com/blog/*`. Ini bertentangan dengan catatan changelog yang saya kutip sebelumnya ("wildcard dan URL berpath tidak didukung"). Pengujian langsung (hasil per format):

| Format | Hasil |
|---|---|
| `*.edu`, `*.com`, `*.org`, `*.go.id`, `*.ac.id`, `*.edu.au` | HTTP 400 (pesan: hanya domain, subdomain, wildcard pattern, domain path; query string, fragmen, regex tidak didukung). Contoh `*.com` di halaman Best Practices pun ditolak. |
| `*.khanacademy.org`, `*.kemendikdasmen.go.id`, `*.ox.ac.uk` | 10 hasil; berfungsi (sama efeknya dengan mendaftarkan domain induk) |
| `khanacademy.org/math/*` | 10 hasil; hanya halaman di bawah `/math/` (tanpa `/standards/`) |
| `murid.kemendikdasmen.go.id/sumber-belajar/*` | 10 hasil; berfungsi |
| `id.khanacademy.org/math/*` dan campuran `www.khanacademy.org/math/*` + `id.khanacademy.org/math/*` + `openstax.org/books/*` | 0 hasil (tidak konsisten; belum jelas penyebabnya) |

Kesimpulan koreksi: wildcard didukung hanya dalam bentuk `*.<domain nyata>`, bukan pola tingkat atas (`*.edu`). Pola path didukung pada sebagian bentuk tetapi perilakunya belum konsisten, jadi dipakai hanya setelah diuji per entri. Kebutuhan awal (`*.edu`, `.org`, `.go.id` sebagai filter kredibilitas) tetap tidak bisa dipenuhi lewat API.

Skor relevansi: tiap hasil membawa field `score`; tidak ada parameter `min_score`. Tavily menganjurkan penyaringan di sisi klien (contoh ambang 0,7; ambang ideal tergantung kasus). Keputusan user (2026-10-27): ambang relevansi ditetapkan 0,7 (lebih ketat dari saran awal 0,5: sumber yang salah atau melenceng lebih berbahaya bagi siswa tunanetra daripada tidak ada sumber). Uji di Fase 6 menilai berapa banyak hasil relevan yang terbuang pada 0,7 dan bisa diturunkan bila terlalu ketat.

## Belum diverifikasi

Apakah `buku.kemendikdasmen.go.id` (SIBI) dan `sma.kemendikdasmen.go.id` menghasilkan teks yang bisa dicari; cakupan pada lebih dari dua pertanyaan; perilaku mode `advanced` (uji memakai `basic`).

## Tindak lanjut

Fase 6: implementasi daftar datar, hapus `search_academic_web` dan Wolfram; uji cakupan 10 pertanyaan.
