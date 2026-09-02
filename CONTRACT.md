# Kontrak Integrasi Lydera

Dokumen ini menjelaskan batas tanggung jawab dan antarmuka antara layanan AI (anotasi), backend (BE), dan frontend (FE). Tujuannya agar setiap tim dapat bekerja tanpa saling bentrok. Isi dokumen mengikuti kondisi kode saat ini.

## 1. Gambaran dan Pembagian Tanggung Jawab

Alur besar: guru mengunggah modul per bab, sistem mengekstrak dan menganotasi isinya menjadi teks siap dibacakan pembaca layar, hasilnya disimpan ke basis data untuk divalidasi guru sebelum dibagikan ke siswa.

| Bagian | Tanggung jawab |
|---|---|
| FE | Antarmuka guru: memilih rentang halaman tiap bab dari preview PDF, mengisi judul modul dan nomor/judul bab, menampilkan hasil anotasi untuk validasi, mengirim feedback. |
| BE | Siklus hidup modul dan bab (identitas, penomoran), pemotongan PDF per bab, penamaan folder output, penyimpanan dan resolusi gambar, memanggil layanan AI, menulis hasil ke DB, logika validasi guru. |
| Layanan AI | Ekstraksi PDF (MinerU), anotasi rumus/tabel/gambar (MLLM), regenerasi satu blok berdasarkan feedback. Tidak menentukan identitas modul/bab, tidak menebak dari nama berkas. |

Prinsip: layanan AI membuat makna, BE menyimpan dan memvalidasi, FE menampilkan. Konsep modul dan bab berasal dari input guru (FE ke BE), bukan dari ekstraksi otomatis.

## 2. Alur End to End

```
FE: guru pilih rentang halaman tiap bab dari preview PDF + isi judul modul, nomor & judul bab
        |
BE: buat module (sekali) -> dapat module_id
    buat chapter per bab  -> dapat chapter_id
    potong PDF per bab
        |
BE -> Layanan AI (per bab):
    1. batch: PDF bab terfokus -> output MinerU per window
    2. annotate: output MinerU -> blok siap-talkback (annotated.json)
    3. ingest: annotated.json -> tabel block di bawah chapter_id
        |
BE: tampilkan hasil ke guru untuk validasi
    guru beri feedback pada satu blok -> BE panggil regenerate() -> update readable_text
```

Satu bab diproses sebagai satu unit. Beberapa bab yang dibuat di bawah `module_id` yang sama otomatis menjadi satu modul.

## 3. Skema Basis Data

Tiga tabel: `module` berisi banyak `chapter`, `chapter` berisi banyak `block`. Definisi ada di `backend/schema.sql`.

module

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | INTEGER | Primary key |
| title | TEXT | Nama modul, dari input guru |
| created_at | TEXT | Waktu pembuatan |

chapter

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | INTEGER | Primary key, unik lintas modul |
| module_id | INTEGER | Referensi ke module(id), cascade saat modul dihapus |
| number | INTEGER | Nomor bab, dari input guru, boleh kosong |
| title | TEXT | Judul bab, dari input guru, boleh kosong |
| source_file | TEXT | Nama berkas PDF bab, boleh kosong |
| created_at | TEXT | Waktu pembuatan |

block

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | INTEGER | Primary key |
| chapter_id | INTEGER | Referensi ke chapter(id), cascade saat bab dihapus |
| reading_order | INTEGER | Urutan baca dalam bab, kelipatan 10 |
| block_type | TEXT | heading, text, formula, table, atau image |
| readable_text | TEXT | Teks yang dibacakan pembaca layar |
| review_priority | TEXT | low, normal, atau high, untuk prioritas pengecekan guru |
| heading_level | INTEGER | Level heading bila ada |
| source_markup | TEXT | Markup asal (LaTeX untuk rumus, HTML untuk tabel) |
| caption | TEXT | Keterangan asli tabel atau gambar |
| image_file | TEXT | Nama berkas gambar, bukan path |
| created_at | TEXT | Waktu pembuatan |

Catatan penting:
- `chapter.id` unik di seluruh tabel, tak berulang antar modul. `number` boleh berulang (tiap modul punya Bab 1).
- `reading_order` dihitung per bab, dimulai dari kelipatan 10, menyambung antar window bab yang sama.
- `image_file` hanya nama berkas (hash konten dari MinerU), bukan path. BE yang me-resolve nama ke lokasi nyata.

## 4. Antarmuka Layanan AI

Semua modul ada di `ai services/annotation/` dan dijalankan dengan uv dari folder itu. Impor antar modul memakai nama datar, sehingga perintah dijalankan dari dalam folder tersebut.

### 4.1 batch (ekstraksi MinerU)

Masukan: satu PDF bab yang sudah terfokus (front matter dan back matter sudah dibuang BE). Keluaran: hasil MinerU per window di `<out>/p{awal}-{akhir}/<stem>/auto/` berisi `content_list.json`, berkas `.md`, dan `images/`.

```
uv run python batch.py --pdf bab.pdf --out output/<chapter_id> [--max-pages 3] \
  [--method auto|txt|ocr] [--no-formula] [--no-table] [--device auto] [--vram N] [--dry-run]
```

- `--out` wajib diisi unik per bab. Konvensi: gunakan `chapter_id` sebagai nama folder (lihat bagian 5).
- `--max-pages` memecah PDF jadi window agar muat di memori. Default 3.
- `--dry-run` mencetak rencana window tanpa menjalankan MinerU.

### 4.2 annotate (anotasi MLLM)

Mengubah `content_list.json` menjadi daftar blok siap-talkback. Rumus, tabel, dan gambar dikonversi lewat MLLM secara paralel, urutan baca dijaga. Fungsi `annotate(content_list_path)` mengembalikan daftar objek dengan field: `block_type`, `reading_order`, `page`, `readable_text`, `review_priority`, `heading_level`, `source_markup`, `caption`, `image_file`. Field `page` hanya untuk penelusuran dan tidak disimpan ke DB.

```
uv run python annotate.py content_list.json [annotated.json]
```

### 4.3 pipeline (orkestrasi anotasi dan ingest satu bab)

Membuat modul dan bab, menganotasi seluruh window sebuah bab, lalu menyimpan bloknya ke DB.

```
uv run python pipeline.py --outputs output/<chapter_id> \
  --module-title "Judul Modul" --chapter-number 1 --chapter-title "Judul Bab" --source-file bab.pdf [--db PATH]
```

Untuk menambah bab ke modul yang sudah ada, ganti `--module-title` dengan `--module-id N`. Nilai judul modul, nomor, dan judul bab berasal dari guru melalui BE.

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

### 4.5 Fungsi backend (penyimpanan)

Di `backend/ingest.py`:

- `create_module(conn, title) -> module_id`
- `create_chapter(conn, module_id, number, title, source_file) -> chapter_id`
- `ingest(conn, annotated_path, chapter_id) -> jumlah_blok`

Koneksi dibuat dengan `db.connect(db_path)` yang mengaktifkan foreign key. Skema dibuat dengan `db.init_db(db_path)`.

## 5. Konvensi dan Aturan

1. Penamaan folder output: gunakan `chapter_id` sebagai `--out`, yaitu `output/<chapter_id>`. `chapter_id` dijamin unik lintas modul, sehingga folder tidak akan pernah bentrok meskipun banyak modul memiliki Bab 2, dan tidak bergantung pada nama berkas PDF.

2. Resolusi gambar: `block.image_file` menyimpan nama berkas saja. BE me-resolve ke lokasi nyata dengan basis folder yang diketahui BE. Karena nama berkas adalah hash konten yang unik global, gambar tidak akan bertabrakan meskipun disimpan flat.

3. Pemrosesan per bab: satu pemanggilan batch dan pipeline menangani satu bab. Grouping bab ke modul terjadi karena bab dibuat di bawah `module_id` yang sama, bukan karena struktur folder.

4. Batas segmentasi bab berasal dari guru (FE), bukan deteksi otomatis. Guru menandai rentang halaman tiap bab dari preview PDF; BE memotong PDF sesuai itu.

5. Konfigurasi lewat environment di `ai services/.env`. Nilai kosong akan jatuh ke default. Variabel: `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `LYDERA_MODEL`, `LYDERA_TEXT_MODEL`, `LYDERA_VISION_MODEL`, `LYDERA_OUTPUT_DIR`, `LYDERA_CACHE_DIR`, `LYDERA_TEXT_MAX_TOKENS`, `LYDERA_VISION_MAX_TOKENS`, `LYDERA_MAX_WORKERS`. Untuk penyimpanan di VPS, set `LYDERA_OUTPUT_DIR` ke lokasi storage tanpa mengubah kode.

## 6. Catatan dan Batasan

1. Keterbatasan mesin: MinerU dengan formula dan tabel aktif berat di memori. Pada mesin uji, `--max-pages 3` aman; nilai lebih besar berisiko gagal karena memori. Kegagalan resource bersifat transien; batch tetap lanjut ke window berikutnya, window yang gagal dapat diulang per rentang.

2. Rate limit MLLM: penyedia dapat mengembalikan 429 pada beban tinggi. Layanan AI sudah punya retry dengan backoff. Menurunkan `LYDERA_MAX_WORKERS` juga mengurangi tekanan.

3. Cache: hasil MLLM di-cache di `.cache/` berdasarkan hash konten, model, dan versi prompt. Menghapus cache aman, hanya membuat panggilan dihitung ulang. Cache dapat dipindah ke Redis nanti tanpa mengubah pemanggil, hanya `cache.py`.

4. Daur ulang id: `chapter.id` dapat didaur ulang setelah penghapusan karena tidak memakai AUTOINCREMENT. Bila `chapter_id` dipakai sebagai nama folder permanen, pertimbangkan menambah AUTOINCREMENT atau membersihkan folder saat bab dihapus.

5. Folder output bersifat debug dan intermediate. Yang wajib dipertahankan untuk produksi adalah `images/` (dirujuk DB) dan opsional `content_list.json` (untuk re-annotate tanpa MinerU ulang). Berkas `.md` tidak dipakai pipeline.
