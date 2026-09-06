# AI Services

Mengubah modul matematika (PDF) menjadi teks siap dibacakan pembaca layar (talkback) untuk siswa tunanetra. Masukan: PDF bab yang halamannya sudah difokuskan (backend membuang bagian depan/belakang sebelum PDF sampai ke sini). Keluaran: blok konten terstruktur, disimpan backend ke PostgreSQL.

Seluruh kode ada di `annotation/`.

## Alur Pipeline

```
PDF bab (terfokus)
  -> run_mineru  ekstraksi layout per rentang halaman (MinerU)
  -> batch       pecah PDF jadi window halaman, jalankan run_mineru per window
  -> preprocess  content_list.json -> daftar blok ter-route
  -> annotate    blok -> teks siap-talkback (rumus/tabel/gambar lewat MLLM)
  -> pipeline    annotate + ingest seluruh window satu bab
  -> ingest (backend, di luar folder ini) -> PostgreSQL
```

Di production, `pipeline.run()` dipanggil oleh `backend/jobs.py` (satu proses worker, lihat `backend/README.md`) — bukan dijalankan manual. CLI di tiap modul (`uv run python xxx.py ...`) ada untuk testing/debug satu tahap secara terpisah.

## Prasyarat

Proyek memakai uv (Python 3.12). Dependensi dan virtual environment ada di root repo, dipakai bersama `backend/`.

Salin `.env.example` menjadi `.env` di folder `ai services/`, isi minimal:

```
OPENROUTER_API_KEY=...
```

Perintah CLI dijalankan dari `ai services/annotation/` memakai `uv run`.

## Konfigurasi

Dibaca `config.py` dari `ai services/.env`.

| Variabel | Default | Keterangan |
|---|---|---|
| `OPENROUTER_API_KEY` | kosong | API Key OpenRouter |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Endpoint OpenRouter |
| `MODEL` | `qwen/qwen3.7-flash` | Model default (teks dan vision) |
| `TEXT_MODEL` | ikut `MODEL` | Override model teks |
| `VISION_MODEL` | ikut `MODEL` | Override model vision |
| `OUTPUT_DIR` | `annotation/output` | Lokasi hasil ekstraksi MinerU |
| `CACHE_DIR` | `annotation/.cache` | Lokasi cache hasil MLLM |
| `TEXT_MAX_TOKENS` | `512` | Batas token panggilan teks |
| `VISION_MAX_TOKENS` | `1024` | Batas token panggilan vision |
| `LLM_MAX_WORKERS` | `4` | Jumlah panggilan LLM paralel saat anotasi |

Nama-nama di atas generik (tidak berprefiks proyek) — cek tidak bentrok kalau proses ini jalan berdampingan dengan layanan lain di mesin yang sama.

`PROMPT_VERSION` (di `config.py`, bukan env) ikut jadi cache key — naikkan nilainya kalau format prompt berubah, supaya cache lama tidak terpakai.

## Modul

**run_mineru.py** — pembungkus CLI MinerU. Ekstrak satu PDF/rentang halaman, simpan `content_list.json` + `.md` + `images/`, hapus file debug.
```
uv run python run_mineru.py --pdf modul.pdf [--out DIR] [--start N] [--end N] \
  [--method auto|txt|ocr] [--no-formula] [--no-table] [--device auto] [--vram N] [--keep-debug]
```

**batch.py** — pecah PDF jadi window sebesar `--max-pages`, jalankan `run_mineru.run` per window ke `<out>/p{awal}-{akhir}/`. Window diproses berurutan.
```
uv run python batch.py --pdf modul.pdf [--out DIR] [--max-pages 3] \
  [--method auto|txt|ocr] [--no-formula] [--no-table] [--device auto] [--vram N] [--dry-run]
```
`--max-pages 0` = satu run untuk seluruh PDF. `--dry-run` = cetak rencana window tanpa menjalankan MinerU.

**preprocess.py** — `preprocess(content_list_path) -> list[Block]`. Ubah `content_list.json` jadi blok ter-route (`heading`, `text`, `formula`, `table`, `image`). Blok `header`/`footer`/`page_number` dibuang. Teks dengan rumus inline `$...$` dipecah jadi segmen.

**annotate.py** — `annotate(content_list_path) -> list[Annotated]`. Heading dan teks lolos langsung (cuma dibersihkan tag/spasi); rumus, tabel, gambar dikonversi lewat MLLM, paralel sebesar `LLM_MAX_WORKERS` tapi urutan baca tetap terjaga. Menghitung `review_priority` untuk membantu guru memprioritaskan pengecekan.
```
uv run python annotate.py content_list.json [annotated.json]
```
Field tiap blok: `block_type`, `reading_order`, `page`, `readable_text`, `review_priority`, `heading_level`, `source_markup`, `caption`, `image_file`. `page` hanya untuk penelusuran, tidak disimpan ke DB.

**formula.py / table.py / image.py** — konversi per jenis blok lewat MLLM + cache.
- `formula.py`: LaTeX -> verbalisasi Bahasa Indonesia (model teks).
- `table.py`: tabel -> linearisasi teks (model vision, dari gambar tabel + HTML hasil OCR).
- `image.py`: gambar/grafik -> deskripsi (model vision).

**llm.py** — klien OpenRouter (SDK openai). `complete_text`, `complete_vision`. Reasoning dimatikan (`extra_body={"reasoning": {"enabled": False}}`). Gambar dikirim sebagai data URI base64.

**cache.py** — cache berbasis file, key = hash(konten, model, `PROMPT_VERSION`). `get(namespace, *parts)` / `put(namespace, value, *parts)`. Tulis atomik. Opsional untuk kebenaran — hapus `.cache/` cuma membuat panggilan MLLM dihitung ulang.

**pipeline.py** — orkestrator satu bab. `run(conn, outputs_dir, chapter_id) -> int` (dipakai `backend/jobs.py`): cari semua `content_list.json` di `outputs_dir`, urutkan per halaman, annotate tiap window, tulis `annotated.json`, lalu `ingest` semuanya ke `chapter_id`. `main()` (CLI, untuk testing manual) juga membuat module/chapter-nya sendiri:
```
uv run python pipeline.py --outputs OUTPUT_DIR/<stem> \
  --module-title "Judul Modul" --fase-id 2 --chapter-number 1 --chapter-title "Judul Bab" \
  --cp-id 3 --source-file bab1.pdf
```
Ganti `--module-title`/`--fase-id` dengan `--module-id N` untuk menambah bab ke modul yang sudah ada. `--fase-id`/`--cp-id` opsional.

**regenerate.py** — titik panggil validasi guru (human in the loop). `regenerate(block_type, feedback, ...)` menghasilkan ulang bacaan satu blok untuk jenis `formula`/`table`/`image` berdasarkan feedback guru. Backend yang memanggil ini lalu menyimpan hasilnya sendiri ke DB — layanan AI tidak menyentuh DB.
```python
regenerate(block_type, feedback, *, source_markup="", image_path=None, caption="", context="")
```

**paths.py** — `setup()` menaruh folder `annotation/` dan `backend/` ke `sys.path`, supaya impor datar (`import config`, dan `import db`/`import ingest` khusus di `pipeline.py`) bisa jalan dari kedua arah tanpa tiap file menghitung ulang lokasinya sendiri.