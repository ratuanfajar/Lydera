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

### Skema Quiz Generator (rancangan, belum ada kode BE/AI yang mengimplementasikannya)

Tujuh tabel tambahan, murni untuk fitur quiz generator yang masih dalam tahap desain. `fase`/`cp` menyimpan data resmi kurikulum (referensi, tidak ikut cascade terhapus). `quiz_request` menyimpan satu request generate (bisa mencakup beberapa bab sekaligus lewat `quiz_request_chapter`). `soal` menyimpan satu soal pilihan ganda hasil generate, dengan `soal_opsi` (opsi jawaban) dan `soal_langkah` (langkah penyelesaian) sebagai anak tabelnya. `soal_stimulus` menyimpan cerita/data yang bisa dipakai bersama oleh beberapa `soal` HOTS sekaligus (lewat `soal.stimulus_id`).

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
| hots_count | INTEGER | Jumlah soal HOTS yang diminta guru |
| lots_count | INTEGER | Jumlah soal LOTS yang diminta guru |
| status | TEXT | queued, running, done, atau failed |
| error | TEXT | Pesan galat bila failed |
| created_at, updated_at | TIMESTAMPTZ | Waktu dibuat/diperbarui |

quiz_request_chapter (tabel penghubung, bab-bab yang dipilih guru untuk satu request)

| Kolom | Tipe | Keterangan |
|---|---|---|
| quiz_request_id | INTEGER | Referensi ke quiz_request(id), cascade |
| chapter_id | INTEGER | Referensi ke chapter(id), cascade |

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
- **`stimulus_id` terisi** (soal bagian dari cluster bersama `soal_stimulus` dan mungkin soal lain yang berbagi stimulus sama, biasanya HOTS): feedback guru memicu LLM meregenerasi **satu cluster penuh** (soal itu + `soal_stimulus`-nya + semua soal lain dengan `stimulus_id` sama), guru approve draft hasilnya sebelum final — bukan langsung dianggap final seperti `regenerate()` di bagian 4.4.

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

### 3.5 Gap yang belum diimplementasikan (perlu FE tahu sebelum desain UI)

- **Edit langsung blok heading/text**: desain manual-edit-tanpa-LLM untuk `block_type` heading/text (lihat bagian 4.4) belum punya endpoint BE. Saat ini tidak ada cara FE mengubah `readable_text` blok jenis ini lewat API.
- **Serve file gambar**: `block.image_file` cuma nama file (hash konten), BE belum punya endpoint yang mengembalikan file/URL gambar aktualnya ke FE. FE belum bisa menampilkan gambar asli untuk blok `block_type=image`/`table` sebagai konteks visual bagi guru.
- **List bab per modul**: tidak ada endpoint `GET /modules/{module_id}/chapters` atau semacamnya. FE tidak punya cara bertanya "modul ini punya bab apa saja" — kalau perlu, FE saat ini harus menyimpan sendiri `chapter_id` yang sudah dibuat, atau BE perlu ditambah endpoint ini.
- **Tidak ada autentikasi/otorisasi**: seluruh endpoint bisa diakses siapa saja tanpa identitas. Tidak ada konsep guru yang login, tidak ada kepemilikan modul per guru — semua modul/bab terlihat oleh siapa pun yang bisa akses BE.
- **Tidak ada endpoint hapus atau edit** modul/bab setelah dibuat. Salah input (judul, fase, rentang halaman) saat ini tidak bisa dikoreksi lewat API — perlu dibuat modul/bab baru, atau intervensi langsung ke DB.

## 4. Interface Layanan AI

Semua modul ada di `ai-services/annotation/` dan dijalankan dengan uv dari folder itu.

### 4.1 batch (ekstraksi MinerU)

Masukan: satu PDF bab yang sudah terfokus (front matter dan back matter sudah dibuang BE). Keluaran: hasil MinerU per window di `<out>/p{awal}-{akhir}/<stem>/auto/` berisi `content_list.json`, file `.md`, dan `images/`.

```
uv run python batch.py --pdf bab.pdf --out output/<chapter_id> [--max-pages 3] \
  [--method auto|txt|ocr] [--no-formula] [--no-table] [--device auto] [--vram N] [--dry-run]
```

- `--out` wajib diisi unik per bab. Konvensi: gunakan `chapter_id` sebagai nama folder (lihat bagian 5).
- `--max-pages` memecah PDF jadi window agar muat di memori. Default 3; nilai lebih besar berisiko gagal karena resource.
- `--dry-run` mencetak rencana window tanpa menjalankan MinerU.
- Kegagalan resource bersifat transien: batch tetap lanjut ke window berikutnya, window yang gagal bisa diulang per rentang tanpa mengulang seluruh bab.

### 4.2 annotate (anotasi MLLM)

Mengubah `content_list.json` menjadi daftar blok siap-talkback. Rumus, tabel, dan gambar dikonversi lewat MLLM secara paralel, urutan baca dijaga. Fungsi `annotate(content_list_path)` mengembalikan daftar objek dengan field: `block_type`, `reading_order`, `page`, `readable_text`, `review_priority`, `heading_level`, `source_markup`, `caption`, `image_file`. Field `page` hanya untuk penelusuran dan tidak disimpan ke DB.

```
uv run python annotate.py content_list.json [annotated.json]
```

Penyedia MLLM bisa mengembalikan 429 pada beban tinggi — sudah ditangani sendiri lewat retry dengan backoff, BE tidak perlu membangun retry untuk kasus ini (menurunkan `LLM_MAX_WORKERS` mengurangi tekanan bila masih sering terjadi).

### 4.3 pipeline (orkestrasi anotasi dan ingest satu bab)

Membuat modul dan bab, menganotasi seluruh window sebuah bab, lalu menyimpan bloknya ke DB.

```
uv run python pipeline.py --outputs output/<chapter_id> \
  --module-title "Judul Modul" --fase-id 2 --chapter-number 1 --chapter-title "Judul Bab" \
  --cp-id 3 --source-file bab.pdf
```

Untuk menambah bab ke modul yang sudah ada, ganti `--module-title`/`--fase-id` dengan `--module-id N`. `--fase-id`/`--cp-id` opsional (boleh kosong). Nilai judul modul, fase, nomor/judul bab, dan cp berasal dari guru melalui BE.

BE dapat memakai `pipeline` langsung, atau memisah tahap dengan memanggil fungsi backend di bagian 4.5.

### 4.4 regenerate (validasi guru, human in the loop)

Menghasilkan ulang bacaan satu blok berdasarkan feedback guru. Berlaku untuk formula, table, dan image. Blok heading dan text diedit langsung tanpa MLLM.

```python
from regenerate import regenerate

teks_baru = regenerate(
    block_type,          # "formula" | "table" | "image"
    feedback,            # teks feedback guru
    source_markup="",    # LaTeX untuk formula, HTML untuk table
    image_path=None,     # path gambar untuk table dan image (BE resolve dari image_file)
    caption="",
    context="",
)
```

BE yang mengambil data blok dari DB, memanggil fungsi ini, lalu memperbarui kolom `readable_text`. Layanan AI tidak menyentuh DB.

### 4.5 Fungsi backend (storage)

Di `backend/ingest.py`:

- `create_module(conn, title, fase_id) -> module_id`
- `create_chapter(conn, module_id, number, title, source_file, cp_id) -> chapter_id`
- `ingest(conn, annotated_path, chapter_id) -> jumlah_blok`

Koneksi dibuat dengan `db.connect()`, memakai `DATABASE_URL` dari environment. Skema dibuat dengan `db.init_db()`.

## 5. Konvensi dan Aturan

1. Penamaan folder output: gunakan `chapter_id` sebagai `--out`, yaitu `output/<chapter_id>`. `chapter_id` dijamin unik lintas modul dan tidak pernah didaur ulang (`SERIAL`), sehingga folder aman dipakai sebagai nama permanen — tidak akan pernah bentrok meskipun banyak modul memiliki Bab 2, dan tidak bergantung pada nama file PDF.

2. Resolve gambar: `block.image_file` menyimpan nama file saja. BE me-resolve ke lokasi nyata dengan basis folder yang diketahui BE. Karena nama file adalah hash konten yang unik global, gambar tidak akan bertabrakan meskipun disimpan flat.

3. Pemrosesan per bab: satu pemanggilan batch dan pipeline menangani satu bab. Grouping bab ke modul terjadi karena bab dibuat di bawah `module_id` yang sama, bukan karena struktur folder.

4. Batas segmentasi bab berasal dari guru (FE), bukan deteksi otomatis. Guru menandai rentang halaman tiap bab dari preview PDF; BE memotong PDF sesuai itu.

5. Retensi folder output: bersifat debug dan intermediate. Yang wajib dipertahankan untuk production adalah `images/` (dirujuk DB) dan opsional `content_list.json` (untuk re-annotate tanpa MinerU ulang). File `.md` tidak dipakai pipeline dan tidak perlu dipertahankan.

6. `POST /blocks/{block_id}/regenerate` tidak menyimpan riwayat: tiap panggilan langsung menimpa `readable_text` yang lama, dan teks feedback guru tidak disimpan ke DB sama sekali. Guru boleh memanggil endpoint ini berkali-kali untuk blok yang sama, tapi FE tidak bisa menampilkan percobaan-percobaan sebelumnya — cuma hasil paling akhir yang ada.
