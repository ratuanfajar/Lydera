# Backend

Penyimpanan hasil anotasi ke basis data. Backend memakai SQLite melalui modul `sqlite3` bawaan Python, tanpa ORM. Skema ditulis portabel agar bisa dipindah ke Postgres.

## Berkas

### schema.sql
Definisi dua tabel: `module` dan `block`.

Tabel `module` menyimpan identitas buku.

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | INTEGER | Primary key |
| `source_file` | TEXT | Nama berkas PDF sumber, unik |
| `title` | TEXT | Nama tampilan modul, diambil dari nama berkas tanpa ekstensi |
| `created_at` | TEXT | Waktu pembuatan baris |

Tabel `block` menyimpan konten per blok yang sudah dianotasi.

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | INTEGER | Primary key |
| `module_id` | INTEGER | Referensi ke `module(id)`, dihapus mengikuti modul |
| `reading_order` | INTEGER | Urutan baca |
| `block_type` | TEXT | `heading`, `text`, `formula`, `table`, atau `image` |
| `readable_text` | TEXT | Teks siap dibacakan pembaca layar |
| `review_priority` | TEXT | `low`, `normal`, atau `high` |
| `heading_level` | INTEGER | Level heading bila ada |
| `source_markup` | TEXT | Markup asal (LaTeX untuk rumus, HTML untuk tabel) |
| `caption` | TEXT | Keterangan asli tabel atau gambar |
| `image_file` | TEXT | Nama berkas gambar, bukan path |
| `created_at` | TEXT | Waktu pembuatan baris |

Indeks `ix_block_module_order` dibuat pada `block(module_id, reading_order)`.

Kolom `image_file` menyimpan nama berkas saja (bukan path), sehingga basis data tidak terikat lokasi penyimpanan. Pemetaan nama berkas ke path atau URL dilakukan oleh pembaca dengan basis folder yang dikonfigurasi.

### db.py
Koneksi dan inisialisasi basis data.

- `connect(db_path=None)` membuka koneksi dengan `row_factory` Row dan `PRAGMA foreign_keys = ON`.
- `init_db(db_path=None)` menjalankan `schema.sql`.

Basis data default berada di `backend/lydera.db`.

### ingest.py
Menyimpan blok dari `annotated.json` ke basis data.

- `ingest(conn, annotated_path, source_file)` membaca `annotated.json`, mencari atau membuat modul berdasarkan `source_file`, lalu menyisipkan blok. Mengembalikan `(module_id, jumlah_blok)`.
- `module_meta(source_file)` menyusun `source_file` dan `title` dari nama berkas.
- `find_or_create_module(conn, meta)` mengembalikan `module_id` yang ada atau membuat baris modul baru.
- `current_max_order(conn, module_id)` mengembalikan `reading_order` terbesar milik modul.

Penyimpanan bersifat bertahap. `reading_order` dihitung dari nilai terbesar yang ada ditambah kelipatan `READING_ORDER_STEP` (10), sehingga beberapa potongan modul yang diproses terpisah tetap menyambung dalam satu modul.

```
uv run python ingest.py annotated.json source_file.pdf
```

## Hubungan dengan AI Service

Orkestrator `pipeline.py` di layanan AI memanggil `ingest.ingest` untuk tiap window sebuah modul secara berurutan, sehingga seluruh blok masuk ke satu baris `module`. Layanan AI menghasilkan `annotated.json`; backend yang menyimpannya ke basis data.

## Catatan

Backend memakai virtual environment uv yang sama dengan layanan AI (berada di root repo). Berkas `*.db` diabaikan Git.
