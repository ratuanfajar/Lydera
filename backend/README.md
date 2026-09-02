# Backend

Penyimpanan hasil anotasi ke basis data. Backend memakai SQLite melalui modul `sqlite3` bawaan Python, tanpa ORM. Skema ditulis portabel agar bisa dipindah ke Postgres.

## Berkas

### schema.sql
Definisi tiga tabel: `module`, `chapter`, dan `block`. Relasinya satu modul memiliki banyak bab, satu bab memiliki banyak blok.

Tabel `module` menyimpan identitas buku. Satu modul dibuat sekali, lalu bab-babnya diunggah ke dalamnya.

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | INTEGER | Primary key |
| `title` | TEXT | Nama modul, mis. Matematika Kelas XI |
| `created_at` | TEXT | Waktu pembuatan baris |

Tabel `chapter` menyimpan tiap bab dalam sebuah modul. Satu baris untuk satu bab yang diunggah.

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | INTEGER | Primary key |
| `module_id` | INTEGER | Referensi ke `module(id)`, dihapus mengikuti modul |
| `number` | INTEGER | Nomor bab, boleh kosong |
| `title` | TEXT | Judul bab, boleh kosong |
| `source_file` | TEXT | Nama berkas PDF bab, boleh kosong |
| `created_at` | TEXT | Waktu pembuatan baris |

Nilai `number`, `title`, dan `source_file` berasal dari input pengunggah, bukan dari ekstraksi otomatis isi dokumen.

Tabel `block` menyimpan konten per blok yang sudah dianotasi.

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | INTEGER | Primary key |
| `chapter_id` | INTEGER | Referensi ke `chapter(id)`, dihapus mengikuti bab |
| `reading_order` | INTEGER | Urutan baca dalam bab |
| `block_type` | TEXT | `heading`, `text`, `formula`, `table`, atau `image` |
| `readable_text` | TEXT | Teks siap dibacakan pembaca layar |
| `review_priority` | TEXT | `low`, `normal`, atau `high` |
| `heading_level` | INTEGER | Level heading bila ada |
| `source_markup` | TEXT | Markup asal (LaTeX untuk rumus, HTML untuk tabel) |
| `caption` | TEXT | Keterangan asli tabel atau gambar |
| `image_file` | TEXT | Nama berkas gambar, bukan path |
| `created_at` | TEXT | Waktu pembuatan baris |

Indeks `ix_chapter_module` pada `chapter(module_id, number)` dan `ix_block_chapter_order` pada `block(chapter_id, reading_order)`.

Kolom `image_file` menyimpan nama berkas saja (bukan path), sehingga basis data tidak terikat lokasi penyimpanan. Pemetaan nama berkas ke path atau URL dilakukan oleh pembaca dengan basis folder yang dikonfigurasi.

### db.py
Koneksi dan inisialisasi basis data.

- `connect(db_path=None)` membuka koneksi dengan `row_factory` Row dan `PRAGMA foreign_keys = ON`.
- `init_db(db_path=None)` menjalankan `schema.sql`.

Basis data default berada di `backend/lydera.db`.

### ingest.py
Membuat modul dan bab, lalu menyimpan blok dari `annotated.json` ke sebuah bab.

- `create_module(conn, title)` membuat baris modul dan mengembalikan `module_id`.
- `create_chapter(conn, module_id, number, title, source_file)` membuat baris bab di bawah modul dan mengembalikan `chapter_id`.
- `ingest(conn, annotated_path, chapter_id)` membaca `annotated.json` dan menyisipkan blok ke bab tersebut. Mengembalikan jumlah blok.
- `current_max_order(conn, chapter_id)` mengembalikan `reading_order` terbesar milik bab.

Penyimpanan blok bersifat bertahap dalam satu bab. `reading_order` dihitung dari nilai terbesar yang ada ditambah kelipatan `READING_ORDER_STEP` (10), sehingga beberapa window dari satu bab yang diproses terpisah tetap menyambung.

Identitas modul dan bab berasal dari pemanggil (backend atau orkestrator), bukan ditebak dari nama berkas. Grouping bab ke modul terjadi karena bab-bab dibuat di bawah `module_id` yang sama.

```
uv run python ingest.py annotated.json "Judul Modul"
```

Perintah di atas membuat satu modul dan satu bab lalu memasukkan blok, sebagai jalur uji ringkas.

## Hubungan dengan AI Service

Layanan AI menghasilkan `annotated.json` per bab. Orkestrator `pipeline.py` di layanan AI membuat modul dan bab lalu memanggil `ingest.ingest` untuk tiap window bab tersebut, sehingga seluruh blok masuk ke satu `chapter` di bawah satu `module`. Untuk menambah bab lain ke modul yang sama, pemanggil memakai `module_id` yang sudah ada.

## Catatan

Backend memakai virtual environment uv yang sama dengan layanan AI (berada di root repo). Berkas `*.db` diabaikan Git.
