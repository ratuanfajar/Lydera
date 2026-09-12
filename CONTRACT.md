# Kontrak Integrasi Lydera

Dokumen ini menjelaskan batas tanggung jawab dan interface antara layanan AI (anotasi), backend (BE), dan frontend (FE). Tujuannya agar setiap tim dapat bekerja tanpa saling bentrok. Isi dokumen mengikuti kondisi kode saat ini.

## 1. Gambaran dan Pembagian Tanggung Jawab

Alur besar: guru upload modul per bab, sistem mengekstrak dan menganotasi isinya menjadi teks siap dibacakan pembaca layar, hasilnya disimpan ke database untuk divalidasi guru sebelum dibagikan ke siswa.

| Bagian | Tanggung jawab |
|---|---|
| FE | Interface guru: memilih fase saat membuat modul, memilih rentang halaman dan domain CP tiap bab dari preview PDF, mengisi judul modul dan nomor/judul bab, menampilkan hasil anotasi untuk validasi, mengirim feedback. |
| BE | Siklus hidup modul dan bab (identitas, penomoran), pemotongan PDF per bab, penamaan folder output, storage dan resolusi gambar, memanggil layanan AI, menulis hasil ke DB, logika validasi guru. |
| Layanan AI | Ekstraksi PDF (MinerU), anotasi rumus/tabel/gambar (MLLM), regenerasi satu blok berdasarkan feedback. Tidak menentukan identitas modul/bab, tidak menebak dari nama file. |


## 2. Skema Database

`module` berisi banyak `chapter`, `chapter` berisi banyak `block` dan diproses lewat satu atau lebih `job`. Definisi lengkap ada di `backend/schema.sql`, memakai PostgreSQL.

module

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | SERIAL | Primary key |
| title | TEXT | Nama modul, dari input guru |
| fase_id | INTEGER | Referensi ke fase(id), boleh kosong |
| created_at | TIMESTAMPTZ | Waktu pembuatan |

chapter

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | SERIAL | Primary key, unik lintas modul |
| module_id | INTEGER | Referensi ke module(id), cascade saat modul dihapus |
| number | INTEGER | Nomor bab, dari input guru, boleh kosong |
| title | TEXT | Judul bab, dari input guru, boleh kosong |
| source_file | TEXT | Nama file PDF bab, boleh kosong |
| cp_id | INTEGER | Referensi ke cp(id), boleh kosong |
| created_at | TIMESTAMPTZ | Waktu pembuatan |

block

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | SERIAL | Primary key |
| chapter_id | INTEGER | Referensi ke chapter(id), cascade saat bab dihapus |
| reading_order | INTEGER | Urutan baca dalam bab, kelipatan 10 |
| block_type | TEXT | heading, text, formula, table, atau image |
| readable_text | TEXT | Teks yang dibacakan pembaca layar |
| review_priority | TEXT | low, normal, atau high, untuk prioritas pengecekan guru |
| heading_level | INTEGER | Level heading bila ada |
| source_markup | TEXT | Markup asal (LaTeX untuk rumus, HTML untuk tabel) |
| caption | TEXT | Keterangan asli tabel atau gambar |
| image_file | TEXT | Nama file gambar, bukan path |
| created_at | TIMESTAMPTZ | Waktu pembuatan |

job

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | SERIAL | Primary key |
| chapter_id | INTEGER | Referensi ke chapter(id) |
| pdf_path | TEXT | Path PDF bab (sudah dipotong) yang diproses |
| out_dir | TEXT | Folder output MinerU untuk bab ini |
| status | TEXT | queued, running, done, atau failed |
| error | TEXT | Pesan galat bila failed |
| blocks_total | INTEGER | Jumlah blok tersimpan bila done |
| created_at, updated_at | TIMESTAMPTZ | Waktu dibuat/diperbarui |

### Skema Quiz Generator

Tujuh tabel tambahan untuk fitur quiz generator. `fase`/`cp` menyimpan data resmi kurikulum (referensi, tidak ikut cascade terhapus). `quiz_request` menyimpan satu request generate (bisa mencakup beberapa bab sekaligus lewat `quiz_request_chapter`). `soal` menyimpan satu soal pilihan ganda hasil generate, dengan `soal_opsi` (opsi jawaban) dan `soal_langkah` (langkah penyelesaian) sebagai anak tabelnya. `soal_stimulus` menyimpan cerita/data yang bisa dipakai bersama oleh beberapa `soal` HOTS sekaligus (lewat `soal.stimulus_id`).

fase

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | SERIAL | Primary key |
| kode | TEXT | 'E' atau 'F', sesuai Fase Kurikulum Merdeka |

cp

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | SERIAL | Primary key |
| fase_id | INTEGER | Referensi ke fase(id) |
| domain | TEXT | Domain Capaian Pembelajaran matematika |
| cp_text | TEXT | Teks resmi Capaian Pembelajaran |

quiz_request

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | SERIAL | Primary key |
| module_id | INTEGER | Referensi ke module(id), cascade saat modul dihapus |
| status | TEXT | queued, running, done, atau failed |
| error | TEXT | Pesan galat bila failed |
| created_at, updated_at | TIMESTAMPTZ | Waktu dibuat/diperbarui |

quiz_request_chapter (tabel penghubung, bab-bab yang dipilih guru untuk satu request, dengan target jumlah soal per bab)

| Kolom | Tipe | Keterangan |
|---|---|---|
| quiz_request_id | INTEGER | Referensi ke quiz_request(id), cascade |
| chapter_id | INTEGER | Referensi ke chapter(id), cascade |
| hots_count | INTEGER | Jumlah soal HOTS yang diminta guru untuk bab ini |
| lots_count | INTEGER | Jumlah soal LOTS yang diminta guru untuk bab ini |

Jumlah soal ditentukan per bab, bukan satu angka gabungan untuk semua bab dalam satu request. Guru menentukan alokasinya sendiri.

soal_stimulus (cerita/data bersama, dipakai satu atau lebih `soal` HOTS sekaligus)

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | SERIAL | Primary key |
| quiz_request_id | INTEGER | Referensi ke quiz_request(id), cascade |
| chapter_id | INTEGER | Bab sumber stimulus ini, cascade |
| source_markup | TEXT | Data/HTML tabel/chart asli (kosong kalau stimulus cuma narasi teks) |
| readable_text | TEXT | Versi interpretasi untuk siswa, selalu terisi |
| review_status | TEXT | pending, approved, rejected, atau edited |
| source_reading_order_start, source_reading_order_end | INTEGER | Rentang reading_order blok sumber di chapter ini |
| created_at | TIMESTAMPTZ | Waktu pembuatan |

soal

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | SERIAL | Primary key |
| quiz_request_id | INTEGER | Referensi ke quiz_request(id), cascade |
| chapter_id | INTEGER | Bab sumber soal ini, cascade |
| stimulus_id | INTEGER | Referensi ke soal_stimulus(id), cascade, boleh kosong (NULL = soal berdiri sendiri) |
| bloom_level | INTEGER | 1-6 (C1-C6); LOTS = 1-3, HOTS = 4-6, dihitung di kode bukan disimpan |
| question_text | TEXT | Teks pertanyaan |
| correct_option | TEXT | Label opsi jawaban benar (A-D) |
| kesimpulan | TEXT | Kalimat penutup yang menegaskan jawaban |
| source_reading_order_start, source_reading_order_end | INTEGER | Rentang reading_order blok sumber di chapter ini, untuk telusur validasi guru |
| review_status | TEXT | pending, approved, rejected, atau edited (guru) |
| review_priority | TEXT | low, normal, atau high; high kalau tahap Validation (LLM re-derive independen) tidak cocok dengan correct_option/langkah hasil Generation |
| validation_notes | TEXT | Catatan hasil Validation, boleh kosong; terisi cuma kalau review_priority = high |
| created_at | TIMESTAMPTZ | Waktu pembuatan |

soal_opsi

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | SERIAL | Primary key |
| soal_id | INTEGER | Referensi ke soal(id), cascade |
| label | TEXT | A, B, C, atau D |
| opsi_text | TEXT | Teks opsi jawaban |

soal_langkah

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | SERIAL | Primary key |
| soal_id | INTEGER | Referensi ke soal(id), cascade |
| urutan | INTEGER | Urutan langkah |
| teks | TEXT | Teks satu langkah penyelesaian |

Human-in-the-loop untuk `soal`, ditentukan oleh `stimulus_id`:
- **`stimulus_id` kosong** (soal berdiri sendiri, biasanya LOTS): guru edit langsung (`question_text`, opsi, `correct_option`, `soal_langkah`, `kesimpulan` sekaligus dalam satu layar) — tanpa keterlibatan LLM, sama seperti blok heading/text di anotasi.
- **`stimulus_id` terisi** (soal bagian dari cluster bersama `soal_stimulus` dan mungkin soal lain yang berbagi stimulus sama, biasanya HOTS): feedback guru memicu LLM meregenerasi **satu cluster penuh** (soal itu + `soal_stimulus`-nya + semua soal lain dengan `stimulus_id` sama), guru approve draft hasilnya sebelum final — bukan langsung dianggap final seperti `regenerate()` di bagian 4.1.

`review_priority`/`validation_notes` diisi oleh tahap Validation (LLM re-derive jawaban secara independen dari `soal_stimulus`/materi sumber, dibandingkan ke `correct_option`/`soal_langkah` hasil Generation) — ini sinyal untuk guru, bukan keputusan otomatis; guru tetap yang memvalidasi akhir.

Mengganti seluruh soal (bukan memperbaiki sebagian) adalah aksi terpisah yang belum didesain skemanya.

Catatan penting:
- `chapter.id` unik di seluruh tabel, tak berulang antar modul. `number` boleh berulang (tiap modul punya Bab 1).
- `reading_order` dihitung per bab, dimulai dari kelipatan 10, menyambung antar window bab yang sama.
- `image_file` hanya nama file (hash konten dari MinerU), bukan path. BE yang me-resolve nama ke lokasi nyata.

## 3. Interface Backend (FE ↔ BE)

Base URL: `http://<host>:8000`. Semua request/response JSON, kecuali `POST /chapters` yang multipart/form-data (upload file). Field wajib yang kosong atau salah tipe otomatis dibalas `422` oleh FastAPI/Pydantic sebelum masuk logika endpoint — tidak dijabarkan per endpoint di bawah.

**GET /health** — cek server hidup, dipakai infra/FE untuk readiness check.
Response: `{status: "ok"}`.

### 3.1 Fase dan CP (referensi kurikulum)

**GET /fase** — daftar fase Kurikulum Merdeka, untuk dropdown saat FE membuat modul.
Response: array `{id, kode}`. `kode` adalah "E" atau "F".

**GET /modules/{module_id}/cp** — daftar domain CP sesuai fase modul ini, untuk dropdown saat FE upload bab.
Response: array `{id, fase_id, domain, cp_text}`. Kosong kalau modul belum punya `fase_id`, atau kalau tidak ada CP untuk domain tertentu di fase itu (lihat bagian 2, tabel `cp`).
Error: `404` kalau `module_id` tidak ditemukan.

### 3.2 Module

**POST /modules** — buat modul baru.
Request body: `{title: string, fase_id: int}`. `fase_id` wajib, harus ada di tabel `fase`.
Response: `{id, title, fase_id, created_at}`.
Error: `400` kalau `fase_id` tidak ditemukan di tabel `fase`.

**GET /modules** — daftar semua modul.
Response: array seperti di atas, urut `id`.

### 3.3 Chapter (upload bab, memicu anotasi)

**POST /chapters** — upload PDF modul + rentang halaman satu bab. Memotong PDF sesuai rentang, membuat baris `chapter`, dan mengantrekan job MinerU + anotasi — diproses async oleh proses worker terpisah (lihat `backend/README.md`), bukan langsung dalam request ini.

Request (multipart/form-data):

| Field | Tipe | Wajib | Keterangan |
|---|---|---|---|
| file | file (PDF) | ya | PDF modul (boleh berisi banyak bab; BE memotong sesuai start_page/end_page) |
| start_page | int | ya | Halaman awal bab ini, 0-based inklusif |
| end_page | int | ya | Halaman akhir bab ini, 0-based inklusif |
| module_id | int | ya | Modul yang sudah dibuat lewat POST /modules |
| number | int | tidak | Nomor bab |
| title | string | tidak | Judul bab |
| cp_id | int | tidak | Dari GET /modules/{module_id}/cp; harus sefase dengan modul |

Response: `{chapter_id, job_id, status}` — `status` selalu `"queued"` di respons ini; progres sesungguhnya dipantau lewat `GET /chapters/{chapter_id}/status`.

Error:
- `400` — `end_page < start_page`, `start_page < 0`, atau `cp_id` tidak ditemukan/tidak sefase dengan modul, atau `start_page`/`end_page` di luar jumlah halaman PDF yang diupload (dilempar `pdf_cut.cut`)
- `404` — `module_id` tidak ditemukan
- `409` — folder output untuk `chapter_id` ini sudah berisi data (chapter baru harusnya tidak pernah kejadian ini; menandakan sisa proses lama yang belum dibersihkan)

**GET /chapters/{chapter_id}** — detail satu bab.
Response: `{id, module_id, number, title, source_file, cp_id, created_at}`.
Error: `404` kalau bab tidak ditemukan.

**GET /chapters/{chapter_id}/status** — status job pemrosesan bab, untuk polling FE.
Response: `{chapter_id, job_id, status, error, blocks_total}`. `status`: `queued` / `running` / `done` / `failed`. `error` terisi kalau `failed`. `blocks_total` terisi kalau `done`.
Error: `404` kalau belum pernah ada job untuk bab ini.

### 3.4 Block (hasil anotasi, validasi guru)

**GET /chapters/{chapter_id}/blocks** — seluruh blok hasil anotasi satu bab, terurut `reading_order`.

Response: array dengan field:

| Field | Keterangan |
|---|---|
| id | ID blok |
| reading_order | Urutan baca |
| block_type | heading / text / formula / table / image |
| readable_text | Teks yang ditampilkan dan dibacakan ke siswa |
| review_priority | low / normal / high — prioritas pengecekan guru |
| heading_level | Level heading, kalau block_type = heading |
| source_markup | LaTeX/HTML asal — ditampilkan sebagai konteks saat guru menulis feedback |
| caption | Keterangan asli tabel/gambar |
| image_file | Nama file gambar (lihat gap di bawah) |

Tidak error kalau `chapter_id` tidak ditemukan — mengembalikan array kosong (endpoint ini tidak memvalidasi keberadaan bab).

**POST /blocks/{block_id}/regenerate** — kirim feedback guru, hasilkan ulang `readable_text` lewat LLM. Berlaku hanya untuk `block_type` formula/table/image.
Request body: `{feedback: string}`.
Response: `{block_id, readable_text}`. `readable_text` baru langsung menimpa yang lama di DB — tidak ada draft/preview, tidak ada riwayat feedback atau hasil sebelumnya yang tersimpan (lihat bagian 5).
Error:
- `404` — blok tidak ditemukan
- `400` — `block_type` blok ini bukan formula/table/image (lihat gap di bawah untuk heading/text)

### 3.6 Quiz Request (generate soal)

**POST /quiz-requests** — buat request generate soal untuk satu atau lebih bab dalam satu modul. Diproses async oleh `quiz_worker.py`.
Request body: `{module_id: int, chapters: [{chapter_id: int, hots_count: int, lots_count: int}, ...]}`. Tiap elemen `chapters` menentukan jumlah soal HOTS/LOTS untuk bab itu secara terpisah.
Response: `{quiz_request_id, status}` — `status` selalu `"queued"` di respons ini.
Error: `400` kalau `chapters` kosong atau ada `chapter_id` yang bukan bagian dari `module_id` ini; `404` kalau `module_id`/`chapter_id` tidak ditemukan.

**GET /quiz-requests/{quiz_request_id}/status** — status pemrosesan, untuk polling FE.
Response: `{quiz_request_id, status, error}`. `status`: `queued` / `running` / `done` / `failed`.
Error: `404` kalau `quiz_request_id` tidak ditemukan.

**GET /quiz-requests/{quiz_request_id}/soal** — daftar seluruh soal hasil generate untuk request ini (semua bab tergabung).
Response: array of `SoalOut` (lihat 3.7).

### 3.7 Soal (review, edit, dan regenerasi guru)

**GET /soal/{soal_id}** — detail satu soal.
Response (`SoalOut`): `{id, chapter_id, stimulus_id, bloom_level, question_text, options: [{label, opsi_text}], correct_option, langkah: [string], kesimpulan, stimulus_text, review_status, review_priority, validation_notes}`. `stimulus_text` diisi dari `soal_stimulus.readable_text` kalau `stimulus_id` tidak kosong, `null` kalau soal berdiri sendiri.
Error: `404` kalau tidak ditemukan.

**PATCH /soal/{soal_id}** — edit langsung tanpa LLM. Hanya berlaku untuk soal berdiri sendiri (`stimulus_id` kosong, biasanya LOTS).
Request body (semua field opsional, kirim yang mau diubah saja): `{question_text?, options?: {"A": "...", ...}, correct_option?, langkah?: [string], kesimpulan?}`. Field apa pun yang terisi men-set `review_status` jadi `edited`.
Response: `SoalOut` (state terbaru).
Error: `404` kalau tidak ditemukan; `400` kalau soal ini punya `stimulus_id` (harus lewat regenerate, bukan PATCH).

**POST /soal/{soal_id}/approve**, **POST /soal/{soal_id}/reject** — set `review_status` jadi `approved`/`rejected`. Tidak ada body.
Response: `{id, review_status}`.

**POST /soal/{soal_id}/regenerate** — feedback guru memicu LLM regenerasi **satu cluster HOTS penuh** (soal ini + semua soal lain yang berbagi `soal_stimulus` yang sama, plus `soal_stimulus`-nya sendiri). Hanya berlaku untuk soal dengan `stimulus_id` terisi.
Request body: `{feedback: string}`.
Response: array of `SoalOut` — seluruh anggota cluster setelah regenerasi. `review_status` tiap soal di cluster dikembalikan ke `pending` (draft baru, bukan otomatis final) — guru approve lagi setelah ini.
Error: `404` kalau tidak ditemukan; `400` kalau soal ini tidak punya `stimulus_id` (harus lewat PATCH, bukan regenerate); `502` kalau regenerasi gagal (LLM error/output tidak valid) — guru disarankan coba lagi.

Catatan penyederhanaan v1: tiap soal di cluster diregenerasi lewat panggilan Generation terpisah; teks `soal_stimulus` final yang dipakai adalah hasil dari soal pertama di cluster, bukan hasil gabungan/konsensus semua panggilan. Karena hasilnya tetap draft (guru approve dulu sebelum final), ketidaksesuaian kecil di titik ini tertangkap saat review manual.

### 3.8 Gap yang belum diimplementasikan (perlu FE tahu sebelum desain UI)

- **Edit langsung blok heading/text**: desain manual-edit-tanpa-LLM untuk `block_type` heading/text (lihat bagian 4.1) belum punya endpoint BE. Saat ini tidak ada cara FE mengubah `readable_text` blok jenis ini lewat API.
- **Serve file gambar**: `block.image_file` cuma nama file (hash konten), BE belum punya endpoint yang mengembalikan file/URL gambar aktualnya ke FE. FE belum bisa menampilkan gambar asli untuk blok `block_type=image`/`table` sebagai konteks visual bagi guru.
- **List bab per modul**: tidak ada endpoint `GET /modules/{module_id}/chapters` atau semacamnya. FE tidak punya cara bertanya "modul ini punya bab apa saja" — kalau perlu, FE saat ini harus menyimpan sendiri `chapter_id` yang sudah dibuat, atau BE perlu ditambah endpoint ini.
- **Tidak ada autentikasi/otorisasi**: seluruh endpoint bisa diakses siapa saja tanpa identitas. Tidak ada konsep guru yang login, tidak ada kepemilikan modul per guru — semua modul/bab terlihat oleh siapa pun yang bisa akses BE.
- **Tidak ada endpoint hapus atau edit** modul/bab setelah dibuat. Salah input (judul, fase, rentang halaman) saat ini tidak bisa dikoreksi lewat API — perlu dibuat modul/bab baru, atau intervensi langsung ke DB.
- **Bloom level soal tidak bisa dipilih spesifik**: guru cuma menentukan jumlah HOTS/LOTS, bukan level C1-C6 yang tepat. Sistem default ke C2 untuk tiap soal LOTS dan C5 untuk tiap soal HOTS (lihat `quiz_pipeline.py`, `_allocate`).
- **List soal per modul (lintas quiz_request)**: `GET /quiz-requests/{id}/soal` cuma menampilkan soal dari satu request. Belum ada endpoint "semua soal yang pernah dibuat untuk modul ini" kalau guru generate berkali-kali.

## 4. Interface Layanan AI

Fungsi berikut dipanggil langsung oleh backend lewat impor datar (lihat `paths.py` tiap folder). Detail modul internal dan CLI tiap tahap ada di `ai services/README.md`, bukan di sini.

### 4.1 Anotasi

Dipanggil dari `backend/jobs.py` untuk memproses satu bab:

- `batch.plan(pdf, out_dir, max_pages) -> list[Window]` — rencana window halaman.
- `run_mineru.run(pdf, out_dir, start=, end=, ...) -> int` — ekstraksi satu window, 0 = sukses.
- `annotation_pipeline.run(conn, outputs_dir, chapter_id) -> int` — anotasi seluruh window bab dan ingest ke DB, mengembalikan jumlah blok.

Dipanggil dari `app/routers/blocks.py` untuk regenerasi satu blok (formula/table/image) berdasarkan feedback guru:

```python
regenerate.regenerate(block_type, feedback, *, source_markup="", image_path=None, caption="", context="") -> str
```

Layanan AI tidak menyentuh DB pada kedua kasus di atas — BE yang membaca/menulis lewat `annotation_ingest.py` (bagian 4.2).

### 4.2 Storage anotasi (backend)

`backend/annotation_ingest.py`, dipanggil dari `app/routers/modules.py`, `chapters.py`, dan `annotation_pipeline.py`:

- `create_module(conn, title, fase_id) -> module_id`
- `create_chapter(conn, module_id, number, title, source_file, cp_id) -> chapter_id`
- `ingest(conn, annotated_path, chapter_id) -> jumlah_blok`

### 4.3 Quiz generator

Dipanggil dari `backend/quiz_worker.py`:

```python
quiz_pipeline.run_for_chapter(conn, quiz_request_id, chapter_id, hots_count, lots_count) -> int
```

Berbeda dari anotasi, `quiz_pipeline.py` menulis langsung ke DB (lewat `backend/quiz_ingest.py`), bukan mengembalikan data untuk BE simpan. Soal digroundkan ke isi bab yang sudah dianotasi lewat prompt chaining (satu model, bukan multi-agent), dengan model `config.QUIZ_MODEL`.

Dipanggil dari `app/routers/soal.py` untuk regenerasi cluster HOTS berdasarkan feedback guru:

```python
regenerate.regenerate_cluster(conn, stimulus_id, feedback) -> list[(soal_id, data, hasil_validasi)]
```

## 5. Konvensi dan Aturan

1. Penamaan folder output: gunakan `chapter_id` sebagai `--out`, yaitu `output/<chapter_id>`. `chapter_id` unik lintas modul dan tidak pernah didaur ulang (`SERIAL`), sehingga folder aman dipakai sebagai nama permanen dan tidak bergantung pada nama file PDF.

2. Resolve gambar: `block.image_file` menyimpan nama file saja. BE me-resolve ke lokasi nyata dengan basis folder yang diketahui BE. Nama file adalah hash konten yang unik global, sehingga gambar tidak bertabrakan meskipun disimpan flat.

3. Pemrosesan per bab: satu pemanggilan batch dan pipeline menangani satu bab. Grouping bab ke modul terjadi lewat `module_id` yang sama, bukan struktur folder.

4. Batas segmentasi bab berasal dari guru (FE), bukan deteksi otomatis. Guru menandai rentang halaman tiap bab dari preview PDF; BE memotong PDF sesuai itu.

5. Retensi folder output: bersifat debug dan intermediate. Wajib dipertahankan untuk production: `images/` (dirujuk DB) dan opsional `content_list.json` (untuk re-annotate tanpa MinerU ulang). File `.md` tidak dipakai pipeline.

6. `POST /blocks/{block_id}/regenerate` tidak menyimpan riwayat: tiap panggilan menimpa `readable_text` yang lama, teks feedback guru tidak disimpan ke DB. FE tidak bisa menampilkan percobaan sebelumnya, cuma hasil paling akhir. Berlaku sama untuk `POST /soal/{id}/regenerate` (bagian 3.7).

7. Model quiz generator (`config.QUIZ_MODEL`, default `openai/gpt-4o`) beda dari model anotasi (`TEXT_MODEL`/`VISION_MODEL`, default `qwen/qwen3.7-flash`) karena reasoning matematika HOTS butuh model lebih kuat. `review_priority=high` dari Validation adalah sinyal untuk guru, bukan keputusan otomatis (lihat bagian 2).

Catatan implementasi layanan AI dan backend (model MinerU in-process, pemisahan proses worker, paralelisasi quiz generator, konvensi penamaan file) ada di `ai services/README.md` dan `backend/README.md` — tidak diulang di sini karena tidak mengubah interface antar tim.
