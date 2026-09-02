# AI Services

Layanan anotasi modul matematika menjadi teks siap dibacakan pembaca layar (talkback) untuk siswa tunanetra. Masukannya berupa PDF modul yang halamannya sudah difokuskan (bagian depan dan belakang dibuang di sisi backend), keluarannya berupa blok konten terstruktur yang disimpan ke basis data.

Seluruh kode berada di folder `annotation/`.

## Alur Pipeline

```
PDF modul (terfokus)
  -> run_mineru: ekstraksi layout per rentang halaman (MinerU)
  -> batch: pecah PDF jadi window halaman, jalankan run_mineru per window
  -> preprocess: content_list.json menjadi daftar blok ter-route
  -> annotate: blok menjadi teks siap-talkback (rumus, tabel, gambar lewat MLLM)
  -> ingest (backend): simpan ke SQLite
```

`pipeline.py` merangkai tahap annotate dan ingest untuk seluruh window sebuah modul.

## Prasyarat

Proyek memakai uv (Python 3.12). Dependensi dan virtual environment berada di root repo dan dipakai bersama backend.

Salin `.env.example` menjadi `.env` di folder `ai services/`, lalu isi kunci OpenRouter:

```
OPENROUTER_API_KEY=...
```

Semua perintah dijalankan dari folder `ai services/annotation/` menggunakan `uv run`.

## Konfigurasi

Dibaca oleh `config.py` dari `ai services/.env`.

| Variabel | Default | Keterangan |
|---|---|---|
| `OPENROUTER_API_KEY` | kosong | Kunci API OpenRouter |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Endpoint OpenRouter |
| `LYDERA_MODEL` | `qwen/qwen3.7-flash` | Model default (teks dan vision) |
| `LYDERA_TEXT_MODEL` | mengikuti `LYDERA_MODEL` | Override model teks |
| `LYDERA_VISION_MODEL` | mengikuti `LYDERA_MODEL` | Override model vision |
| `LYDERA_OUTPUT_DIR` | `annotation/output` | Lokasi hasil ekstraksi MinerU |
| `LYDERA_CACHE_DIR` | `annotation/.cache` | Lokasi cache hasil MLLM |
| `LYDERA_TEXT_MAX_TOKENS` | `512` | Batas token panggilan teks |
| `LYDERA_VISION_MAX_TOKENS` | `1024` | Batas token panggilan vision |
| `LYDERA_MAX_WORKERS` | `4` | Jumlah thread paralel saat anotasi |

`PROMPT_VERSION` didefinisikan di `config.py` dan menjadi bagian kunci cache; menaikkannya membuat cache lama tidak lagi dipakai.

## Modul

### run_mineru.py
Pembungkus CLI MinerU (dipanggil sebagai `python -m mineru.cli.client`). Menjalankan MinerU untuk satu PDF atau rentang halaman, menyimpan `content_list.json`, berkas `.md`, dan folder `images/`, lalu menghapus berkas debug. Menyediakan fungsi `run(pdf, out, ...)` yang dipakai `batch.py` secara langsung.

```
uv run python run_mineru.py --pdf modul.pdf [--out DIR] [--start N] [--end N] \
  [--method auto|txt|ocr] [--no-formula] [--no-table] [--device auto] [--vram N] [--keep-debug]
```

### batch.py
Menerima PDF modul yang sudah terfokus, memecah seluruh halamannya menjadi window sebesar `--max-pages`, lalu menjalankan `run_mineru.run` per window ke folder terpisah `<out>/p{awal}-{akhir}/`. Window diproses berurutan menurut halaman.

```
uv run python batch.py --pdf modul.pdf [--out DIR] [--max-pages 3] \
  [--method auto|txt|ocr] [--no-formula] [--no-table] [--device auto] [--vram N] [--dry-run]
```

`--max-pages 0` memproses seluruh PDF dalam satu run. `--dry-run` mencetak rencana window tanpa menjalankan MinerU.

### preprocess.py
Mengubah `content_list.json` MinerU menjadi daftar `Block` ter-route (heading, text, formula, table, image). Blok jenis header, footer, dan nomor halaman dibuang. Teks yang memuat rumus inline `$...$` dipecah menjadi segmen.

### annotate.py
Mengubah daftar blok menjadi daftar `Annotated`. Heading dan teks diproses langsung (passthrough dengan pembersihan tag dan spasi), sedangkan rumus, tabel, dan gambar dikonversi lewat MLLM. Panggilan MLLM dijalankan paralel dengan thread pool sebesar `MAX_WORKERS`, namun urutan baca tetap dijaga. Menghitung `review_priority` untuk membantu guru memprioritaskan pengecekan.

```
uv run python annotate.py content_list.json [annotated.json]
```

Field pada tiap blok hasil: `block_type`, `reading_order`, `page`, `readable_text`, `review_priority`, `heading_level`, `source_markup`, `caption`, `image_file`. Field `page` hanya untuk penelusuran dan tidak disimpan ke basis data.

### formula.py, table.py, image.py
Konversi per jenis blok memakai MLLM dan cache.

- `formula.py`: verbalisasi rumus LaTeX ke Bahasa Indonesia lewat model teks.
- `table.py`: linearisasi tabel lewat model vision (gambar tabel dan HTML hasil OCR).
- `image.py`: deskripsi gambar atau grafik lewat model vision.

### llm.py
Klien OpenRouter berbasis SDK openai. Menyediakan `complete_text` dan `complete_vision`. Penalaran model dimatikan lewat `extra_body={"reasoning": {"enabled": False}}`. Gambar dikirim sebagai data URI base64.

### cache.py
Cache berbasis berkas dengan kunci hash dari konten, model, dan `PROMPT_VERSION`. Antarmuka `get(namespace, *parts)` dan `put(namespace, value, *parts)`. Penulisan bersifat atomik. Cache bersifat opsional untuk kebenaran; menghapus isi `.cache/` hanya membuat panggilan MLLM dihitung ulang.

### pipeline.py
Orkestrator anotasi dan penyimpanan untuk satu bab. Membuat modul dan bab, mencari seluruh `content_list.json` di folder output, mengurutkannya menurut halaman, menganotasi tiap window, menulis `annotated.json` per folder, lalu memanggil ingest backend agar semua blok masuk ke satu bab.

```
uv run python pipeline.py --outputs OUTPUT_DIR/<stem> \
  --module-title "Judul Modul" --chapter-number 1 --chapter-title "Judul Bab" --source-file bab1.pdf [--db PATH]
```

Untuk menambah bab lain ke modul yang sudah ada, ganti `--module-title` dengan `--module-id N`. Nilai nomor dan judul bab berasal dari pemanggil, bukan dari ekstraksi otomatis.

### regenerate.py
Titik panggil untuk alur validasi guru (human in the loop). Fungsi `regenerate(block_type, feedback, ...)` menghasilkan ulang bacaan satu blok berdasarkan feedback guru untuk jenis formula, table, dan image. Backend memanggil fungsi ini lalu memperbarui basis data sendiri; layanan AI tidak menyentuh basis data.

```python
regenerate(block_type, feedback, *, source_markup="", image_path=None, caption="", context="")
```

## Catatan

Modul di `annotation/` saling mengimpor dengan nama datar (mis. `import config`), sehingga perintah dijalankan dari dalam folder `annotation/`. Folder `output/` dan `.cache/` diabaikan Git.
