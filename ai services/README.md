# AI Services

Dua fitur: **anotasi** (`annotation/`) mengubah modul matematika (PDF) jadi teks siap dibacakan pembaca layar, dan **quiz generator** (`quiz/`) menghasilkan soal pilihan ganda dari modul yang sudah dianotasi. Keduanya menyimpan hasilnya ke PostgreSQL lewat `backend/`.

## Alur Pipeline — Anotasi

```
PDF bab
  -> run_mineru         ekstraksi layout per rentang halaman (MinerU)
  -> batch               pecah PDF jadi window halaman, jalankan run_mineru per window
  -> preprocess          content_list.json -> daftar blok ter-route
  -> annotate            blok -> teks siap-talkback (rumus/tabel/gambar lewat MLLM)
  -> annotation_pipeline annotate + ingest seluruh window satu bab
  -> annotation_ingest (backend) -> PostgreSQL
```

Di production, `annotation_pipeline.run()` dipanggil oleh `backend/jobs.py` (proses worker, lihat `backend/README.md`). CLI di tiap modul (`uv run python xxx.py ...`) dipakai untuk testing/debug satu tahap secara terpisah.

## Alur Pipeline — Quiz Generator

```
block yang sudah dianotasi (satu bab, di DB)
  -> segment    pecah jadi segmen berdasar heading "A."/"B."/"C." (tanpa LLM)
  -> context    ringkas tiap segmen (map), gabung jadi ringkasan bab (reduce)
  -> generate   satu segmen + ringkasan bab -> satu soal (JSON)
  -> validate   re-derive jawaban independen dari sumber yang sama, bandingkan ke generate
  -> quiz_pipeline -> quiz_ingest (backend) -> PostgreSQL
```

Beda dari anotasi: `quiz_pipeline.py` memanggil DB langsung lewat `backend/quiz_ingest.py`. Modul konversi individualnya (`segment.py`, `context.py`, `generate.py`, `validate.py`) tidak menyentuh DB. Di production, dipanggil `backend/quiz_worker.py` (proses worker terpisah, lihat `backend/README.md`).

## Prasyarat

Proyek memakai uv (Python 3.12). Dependensi dan virtual environment ada di root repo, dipakai bersama `backend/`.

Salin `.env.example` menjadi `.env` di folder `ai services/`, isi minimal:

```
OPENROUTER_API_KEY=...
```

Perintah CLI dijalankan dari `ai services/annotation/` atau `ai services/quiz/` (sesuai fiturnya) memakai `uv run`.

## Konfigurasi

Dibaca `config.py` dari `ai services/.env`.

| Variabel | Default | Keterangan |
|---|---|---|
| `OPENROUTER_API_KEY` | kosong | API Key OpenRouter |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Endpoint OpenRouter |
| `MODEL` | `qwen/qwen3.7-flash` | Model default (teks dan vision) |
| `TEXT_MODEL` | ikut `MODEL` | Override model teks (anotasi) |
| `VISION_MODEL` | ikut `MODEL` | Override model vision (anotasi) |
| `QUIZ_MODEL` | `openai/gpt-4o` | Model quiz generator |
| `OUTPUT_DIR` | `annotation/output` | Lokasi hasil ekstraksi MinerU |
| `CACHE_DIR` | `annotation/.cache` | Lokasi cache hasil MLLM |
| `TEXT_MAX_TOKENS` | `512` | Batas token panggilan teks |
| `VISION_MAX_TOKENS` | `1024` | Batas token panggilan vision |
| `LLM_MAX_WORKERS` | `4` | Jumlah panggilan LLM paralel (anotasi dan quiz generator) |

Nama variabel di atas generik (tidak berprefiks proyek) — cek tidak bentrok kalau proses ini jalan berdampingan dengan layanan lain di mesin yang sama.

`PROMPT_VERSION` (di `config.py`, bukan env) ikut jadi cache key — naikkan nilainya kalau format prompt berubah, supaya cache lama tidak terpakai.

`QUIZ_MODEL` beda dari `TEXT_MODEL`/`VISION_MODEL` karena reasoning matematika HOTS butuh model lebih kuat dari model default anotasi. Detail perbandingan ada di `CONTRACT.md` bagian 5.

## Modul (annotation/)

**run_mineru.py** — ekstrak satu PDF/rentang halaman lewat `mineru.cli.common.do_parse` in-process (bukan subprocess CLI), simpan `content_list.json` + `.md` + `images/`, hapus file debug. Model MinerU di-cache sebagai singleton dalam proses (`mineru/backend/pipeline/model_init.py`); dipanggil dari proses long-running (`backend/annotation_worker.py`), model cuma di-load sekali per proses, bukan per window.
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

**annotate.py** — `annotate(content_list_path) -> list[Annotated]`. Heading dan teks dibersihkan tag/spasi tanpa LLM; rumus, tabel, gambar dikonversi lewat MLLM, paralel sebesar `LLM_MAX_WORKERS`, urutan baca tetap terjaga. Menghitung `review_priority` untuk membantu guru memprioritaskan pengecekan.
```
uv run python annotate.py content_list.json [annotated.json]
```
Field tiap blok: `block_type`, `reading_order`, `page`, `readable_text`, `review_priority`, `heading_level`, `source_markup`, `caption`, `image_file`. `page` hanya untuk penelusuran, tidak disimpan ke DB.

**formula.py / table.py / image.py** — konversi per jenis blok lewat MLLM + cache.
- `formula.py`: LaTeX -> verbalisasi Bahasa Indonesia (model teks).
- `table.py`: tabel -> linearisasi teks (model vision, dari gambar tabel + HTML hasil OCR).
- `image.py`: gambar/grafik -> deskripsi (model vision).

**llm.py** — klien OpenRouter (SDK openai). `complete_text`, `complete_vision`. Reasoning dimatikan (`extra_body={"reasoning": {"enabled": False}}`). Gambar dikirim sebagai data URI base64.

**cache.py** — cache berbasis file, key = hash(konten, model, `PROMPT_VERSION`). `get(namespace, *parts)` / `put(namespace, value, *parts)`. Tulis atomik. Menghapus `.cache/` membuat panggilan MLLM dihitung ulang.

**annotation_pipeline.py** — orkestrator satu bab. `run(conn, outputs_dir, chapter_id) -> int` (dipakai `backend/jobs.py`): cari semua `content_list.json` di `outputs_dir`, urutkan per halaman, annotate tiap window, tulis `annotated.json`, lalu `annotation_ingest` ke `chapter_id`. `main()` (CLI, testing manual) juga membuat module/chapter-nya sendiri:
```
uv run python annotation_pipeline.py --outputs OUTPUT_DIR/<stem> \
  --module-title "Judul Modul" --fase-id 2 --chapter-number 1 --chapter-title "Judul Bab" \
  --cp-id 3 --source-file bab1.pdf
```
Ganti `--module-title`/`--fase-id` dengan `--module-id N` untuk menambah bab ke modul yang sudah ada. `--fase-id`/`--cp-id` opsional.

**regenerate.py** — titik panggil validasi guru. `regenerate(block_type, feedback, ...)` menghasilkan ulang bacaan satu blok untuk jenis `formula`/`table`/`image` berdasarkan feedback guru. Backend menyimpan hasilnya ke DB — layanan AI tidak menyentuh DB.
```python
regenerate(block_type, feedback, *, source_markup="", image_path=None, caption="", context="")
```

**paths.py** — `setup()` menaruh folder `annotation/` dan `backend/` ke `sys.path`, supaya impor datar (`import config`, `import db`/`import annotation_ingest`) bisa jalan dari kedua arah.

## Modul (quiz/)

**segment.py** — tanpa LLM. `build_segments(chapter_id, blocks) -> list[Segment]`. Pecah block satu bab (urut `reading_order`) jadi segmen berdasar heading berpola `A.`/`B.`/`C.` (regex `^[A-Z]\.\s`, bukan `heading_level` — MinerU tidak membedakan level heading secara berjenjang). Block sebelum sub-bab pertama tidak masuk segmen apa pun.

**context.py** — ringkasan berjenjang (map-reduce), dua fungsi, dua-duanya dicache dengan key yang ikut `QUIZ_MODEL`:
- `summarize_segment(segment) -> str`: 1-2 kalimat ringkasan satu segmen (map).
- `summarize_chapter(segment_summaries) -> str`: gabungan semua ringkasan segmen satu bab jadi satu paragraf (reduce).

Mencegah loss-in-the-middle di `generate.py`: segmen kecil diberi teks penuh, segmen lain cuma lewat ringkasannya. Bukan RAG — tidak ada vektorisasi atau similarity search; scope materi sudah ditentukan guru.

**generate.py** — `generate_soal(segment, chapter_summary, bloom_level, feedback="") -> dict`. Hasilkan satu soal (JSON: `question_text`, `options`, `correct_option`, `langkah`, `kesimpulan`, `stimulus`) dari satu segmen + ringkasan bab. Tidak dicache. `feedback` diisi saat regenerasi dari koreksi guru (lihat `regenerate.py`). Token budget beda LOTS/HOTS (`LOTS_MAX_TOKENS`/`HOTS_MAX_TOKENS`).

**validate.py** — `validate_soal(segment, question_text, options, correct_option, stimulus_text="") -> dict`. LLM re-derive jawaban independen dari sumber yang sama (blind ke hasil Generation), kembalikan `{matches, derived_option, derived_langkah}`. Tidak dicache. `matches=False` bukan keputusan otomatis — validator sendiri bisa berhalusinasi, jadi hasil ini jadi sinyal untuk guru (lihat `CONTRACT.md` bagian 5).

**regenerate.py** — `regenerate_cluster(conn, stimulus_id, feedback) -> list[(soal_id, data, hasil_validasi)]`. Dipanggil backend saat guru kasih feedback ke soal HOTS (`stimulus_id` terisi): regenerasi ulang seluruh cluster (soal itu + semua soal lain yang berbagi `soal_stimulus` sama). Beda dari `annotation/regenerate.py`, modul ini menyentuh DB langsung untuk merekonstruksi segmen dan ringkasan bab dari data yang sudah tersimpan.

**quiz_pipeline.py** — orkestrator satu bab, menyentuh DB langsung. `run_for_chapter(conn, quiz_request_id, chapter_id, hots_count, lots_count) -> int`: segmentasi, ringkas, generate + validate tiap soal, simpan lewat `backend/quiz_ingest.py`. Map (per segmen) dan Generation+Validation (per soal) dijalankan paralel sebesar `LLM_MAX_WORKERS` lewat `ThreadPoolExecutor`; urutan hasil tetap sama seperti sekuensial. Penulisan ke DB tetap satu-satu di thread utama. `main()` (CLI, testing manual) bisa bikin `quiz_request` sendiri kalau `--quiz-request-id` tidak diberi:
```
uv run python quiz_pipeline.py --chapter-id 6 --lots 1 --hots 1 [--quiz-request-id N]
```

**jsonutil.py** — `parse_json(raw) -> dict`. Toleran terhadap code fence markdown dan backslash yang bukan escape sequence JSON valid (notasi LaTeX seperti `\%`/`\rightarrow`).

**paths.py** — `setup()` menaruh folder `quiz/`, `annotation/`, dan `backend/` ke `sys.path`. File spesifik satu fitur diberi prefiks nama fiturnya (`quiz_pipeline.py`/`annotation_pipeline.py`, `quiz_worker.py`/`annotation_worker.py`, `quiz_ingest.py`/`annotation_ingest.py`) karena keduanya berbagi `sys.path` yang sama.
