# AI Services

Empat fitur: **Annoter** (`annoter/`) mengubah modul matematika (PDF) jadi teks siap dibacakan pembaca layar, **Quizzer** (`quizzer/`) menghasilkan soal pilihan ganda dari modul yang sudah dianotasi, **Evaluaizer** (`evaluaizer/`) menganalisis jawaban siswa yang salah, dan **Clarifier** (`clarifier/`) menjawab pertanyaan siswa berbasis RAG dari modul yang sama. Kode bersama (konfigurasi Azure, klien LLM, cache, format prompt) ada di `common/`. Hasil semua fitur disimpan ke PostgreSQL lewat `backend/`.

## Alur Pipeline — Annoter

```
PDF bab
  -> run_mineru         ekstraksi layout per rentang halaman (MinerU)
  -> batch              pecah PDF jadi window halaman, jalankan run_mineru per window
  -> preprocess         content_list.json -> daftar blok ter-route
  -> annotate           blok -> teks siap-talkback (rumus/tabel/gambar lewat MLLM)
  -> annoter_pipeline   annotate tiap window satu bab -> annotated.json per window
  -> ContentService.ingest_annotated_json (backend) -> PostgreSQL
```

Di production, `process_mineru_job_task` (`backend/app/tasks/mineru_tasks.py`, worker taskiq) memanggil `run_mineru.run_async` lalu `annoter_pipeline.run_with_report()` (blok atau window yang gagal dilewati dan ditandai; error bila lebih dari 30% atau layanan LLM putus), kemudian backend menyimpan blok lewat `ContentService.ingest_annotated_json`. CLI di tiap modul (`uv run python -m annoter.<modul> ...` dari `ai-services/`) dipakai untuk testing/debug satu tahap secara terpisah.

Alur satu blok gambar di `annotate`:

```
gambar
  -> klasifikasi percobaan 1 (tanpa konteks)
  -> klasifikasi percobaan 2 (dengan teks tetangga, maksimal 400 karakter)
  -> klasifikasi percobaan 3 (penentu akhir: gambar + hasil 1 dan 2 + alasannya)
  -> dekoratif dan yakin (4 atau lebih): dilewati, teks kosong
  -> selain itu: deskripsi dengan prompt per jenis (prompt umum bila jenis tidak pasti)
```

## Alur Pipeline — Quizzer

Semua bab yang dipilih guru diproses bersama dalam satu panggilan `quizzer_pipeline.compute_for_quiz`. Rancangan lengkap: `docs/specs/0001-pipeline-quizzer-plan-then-generate.md`.

```
blok tiap bab (di DB) + CP bab + kuota HOTS/LOTS per bab dari guru
  -> segment        potong berdasar blok dan karakter (target 4.000, maksimal 8.000), heading hanya memilih titik potong
  -> points         LLM mengekstrak poin materi per segmen (di-cache), lalu poin kembar antar segmen dibuang (kemiripan kata)
  -> mapping        LLM mengusulkan poin untuk tiap slot (bab, level); kode menegakkan kuota dan mengisi kekurangan
  -> generate       satu soal per slot dari poin + teks sumbernya (LOTS tanpa stimulus; HOTS wajib stimulus: teks, tabel, gambar SVG, atau campuran, dipilih model)
  -> checks         kode: struktur opsi, rujukan visual, kunci jauh lebih panjang dari opsi lain
  -> shuffle        kode: acak urutan opsi dengan target kunci seimbang per bab
  -> validate       model validator lintas keluarga: jawab buta + audit langkah dan kesimpulan
  -> perbaikan      satu kali regenerasi dengan daftar masalah dari pemeriksaan kode atau temuan audit berat sebagai koreksi; yang masih bermasalah hanya ditandai
  -> laporan        coverage_report (poin terpakai, diminta vs jadi, slot gagal, diperbaiki)
```

Semua modul di `ai-services/quizzer/` murni komputasi. Backend (`backend/app/tasks/quiz_tasks.py`, taskiq) membaca blok dan CP dari DB, memanggil `compute_for_quiz`, lalu menyimpan soal, `source_point`, dan `coverage_report` lewat `backend/app/domains/quizzer/repositories/repository.py`. Satu slot yang gagal tidak membatalkan yang lain.

## Prasyarat

Proyek memakai uv (Python 3.12). Dependensi dan virtual environment ada di root repo, dipakai bersama `backend/`.

Salin `.env.example` menjadi `.env` di folder `ai-services/`, isi minimal:

```
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://<nama-resource>.openai.azure.com/
```

Model yang dipakai adalah nama *deployment* di resource Azure itu: `gpt-5.4-mini` dan `text-embedding-3-large` (embedding).

Perintah CLI dijalankan dari `ai-services/` sebagai modul paket, mis. `uv run python -m annoter.annotate content_list.json annotated.json`.

## Menjalankan secara runut

`ai-services/` bukan server: ia pustaka komputasi murni yang dipanggil backend (API dan worker taskiq) dan tidak menyentuh database. Ada dua cara menjalankannya.

### A. Lewat sistem penuh (backend)

Semua perintah dari root repo kecuali disebut lain.

1. Pasang dependensi: `uv sync`.
2. Siapkan env: salin `ai-services/.env.example` ke `ai-services/.env` (kunci Azure, opsional `SEARCH_API_KEY`) dan `backend/.env.example` ke `backend/.env` (database, Redis, JWT). Jangan commit file `.env`.
3. Nyalakan PostgreSQL dengan ekstensi pgvector dan Redis.
4. Migrasi database: `cd backend && uv run alembic upgrade head`.
5. API: `cd backend && uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` (pakai `python -m` bila `uvicorn` gagal dengan `Failed to canonicalize script path`).
6. Worker taskiq di terminal lain: `cd backend && uv run taskiq worker app.core.taskiq:broker app.tasks.mineru_tasks app.tasks.quiz_tasks app.tasks.process_exam_review_tasks app.tasks.chatbot_tasks app.tasks.progress_tasks app.tasks.email_tasks app.tasks.file_tasks app.tasks.evaluaizer_tasks`.
7. Periksa: `GET http://localhost:8000/health` dan dokumentasi di `/docs`.
8. Urutan alur data (Postman "Lydera" berisi contoh tiap langkah):
   1. Guru mengunggah PDF bab: worker menjalankan MinerU lalu Annoter (butuh waktu beberapa menit per bab).
   2. Guru meninjau blok hasil anotasi, mengonfirmasi (ingest ke DB), lalu mempublikasikan modul.
   3. Clarifier diindeks: otomatis oleh worker begitu anotasi satu bab selesai (siswa baru melihat hasilnya setelah modul dipublikasikan). Edit blok sesudahnya tidak memicu reindex otomatis; panggil manual `POST /api/clarifier/chapters/{id}/reindex` atau `POST /api/clarifier/classrooms/{id}/reindex` (peran guru). Wajib dijalankan ulang untuk bab yang sudah ada setelah chunker berubah.
   4. Guru membuat kuis (Quizzer, progres lewat SSE), meninjau atau mengedit soal, lalu mempublikasikannya.
   5. Siswa mengerjakan kuis; Evaluaizer menganalisis jawaban salah yang punya langkah. Selama kuis berlangsung Clarifier dikunci untuk siswa itu.
   6. Siswa memakai Clarifier (tanya jawab dan latihan soal di chat) di luar waktu kuis.

### B. Tanpa database, lewat CLI per modul

Dari folder `ai-services/` (butuh `ai-services/.env`; hanya Annoter yang butuh MinerU dan modelnya):

1. Ekstraksi layout satu PDF: `uv run python -m annoter.run_mineru --pdf <berkas.pdf> --out annoter/output/<bab>`, atau seluruh PDF per window halaman: `uv run python -m annoter.batch --pdf <berkas.pdf> --out annoter/output/<bab>`.
2. Anotasi semua window satu bab (tanpa ingest ke DB): `uv run python -m annoter.annoter_pipeline --outputs annoter/output/<bab>`. Satu window saja: `uv run python -m annoter.annotate <content_list.json> <annotated.json>`.
3. Quizzer, Evaluaizer, dan Clarifier tidak punya CLI produksi karena butuh data dari DB; fungsinya dipanggil backend. Untuk mencoba: `evaluaizer/eval/run_eval.py` (36 panggilan Azure) dan skrip di `quizzer/eval/`. Kedua jenis skrip ini memanggil Azure dan berbayar, jalankan hanya saat perlu.
4. Tes murni tanpa jaringan, DB, atau LLM nyata, dari root repo: `uv run pytest -q`.

## Konfigurasi

Dibaca `config.py` dari `ai-services/.env`.

| Variabel | Default | Keterangan |
|---|---|---|
| `AZURE_OPENAI_API_KEY` | kosong | API Key resource Azure OpenAI |
| `AZURE_OPENAI_ENDPOINT` | kosong | Endpoint resource (hanya host-nya yang dipakai; endpoint project tidak dipakai) |
| `CHAT_MODEL` | `gpt-5.4-mini` | Model chatbot (effort `low`) |
| `CHAT_MAX_TOKENS` | `1024` | Batas token jawaban chatbot |
| `MAX_TOOL_ITERATIONS` | `10` | Batas putaran tool calling chatbot |
| `TOP_K_CHUNKS` | `5` | Jumlah chunk hasil `search_module` |
| `EMBEDDING_API_KEY` / `EMBEDDING_BASE_URL` | kunci dan endpoint Azure di atas | Client embedding terpisah (opsional) |
| `EMBEDDING_MODEL` | `text-embedding-3-large` | Model embedding |
| `EMBEDDING_DIM` | `3072` | Dimensi vektor; harus sama dengan kolom pgvector dan setting backend |
| `SCOPE_SIM_HIGH` / `SCOPE_SIM_LOW` | `0.60` / `0.30` | Ambang similarity scope gate chatbot |
| `SEARCH_API_KEY` / `SEARCH_API_URL` | kosong / `https://api.tavily.com/search` | Pencarian sumber OER (Clarifier) |
| `OER_MIN_SCORE` | `0.6` | Skor relevansi minimum hasil pencarian OER |
| `QUIZ_MARKUP_ENABLED` | kosong (menyala) | Isi `0` agar soal ditulis tanpa LaTeX; samakan nilainya di API dan worker |
| `QUIZ_STIMULUS_TYPES` | kosong (semua jenis) | Jenis stimulus yang boleh dipilih model, dipisah koma (`tabel`, `gambar`, `campuran`); `teks` membatasi ke stimulus teks; samakan di API dan worker |

Konstanta bersama ada di `common/config.py` (bukan env, ubah lewat kode):

| Konstanta | Nilai | Keterangan |
|---|---|---|
| `TEXT_MODEL` / `TEXT_EFFORT` | `gpt-5.4-mini` / `none` | Model rumus |
| `VISION_MODEL` / `VISION_EFFORT` | `gpt-5.4-mini` / `none` | Model tabel dan gambar (klasifikasi dan deskripsi) |
| `REASONING_EFFORT` | `low` | Effort fitur yang menalar (Quizzer, Evaluaizer, Clarifier) |
| `TEXT_MAX_TOKENS` | `512` | Batas token panggilan teks |
| `VISION_MAX_TOKENS` | `1800` | Batas token panggilan vision |
| `LLM_MAX_WORKERS` | `4` | Jumlah panggilan LLM paralel |
| `CACHE_DIR` | `ai-services/.cache` | Lokasi cache hasil MLLM |
| `FORMULA_PROMPT_VERSION` | `3` | Kunci cache rumus; naikkan bila prompt rumus berubah (tidak menghapus cache tabel dan gambar) |
| `TABLE_PROMPT_VERSION` | `5` | Kunci cache tabel; naikkan bila prompt tabel berubah |
| `TABLE_MAX_TOKENS` | `4000` | Batas keluaran model penglihatan untuk tabel (memuat seluruh sel) |
| `PROMPT_VERSION` | `13` | Ikut jadi cache key; naikkan kalau prompt atau model anotasi berubah supaya cache lama tidak terpakai |

Konstanta per fitur ada di `<fitur>/config.py`. Annoter (`annoter/config.py`): `OUTPUT_DIR` (`annoter/output`, lokasi hasil ekstraksi MinerU; backend memakai setting `OUTPUT_DIR` sendiri), `CLASSIFY_MAX_TOKENS` (`300`), `CLASSIFY_CONTEXT_CHARS` (`400`, teks tetangga untuk percobaan 2 dan 3), `CLASSIFY_MIN_CONFIDENCE` (`4`, keyakinan minimal agar gambar dekoratif dilewati). Quizzer (`quizzer/config.py`): `QUIZ_MODEL` `gpt-5.4-mini` dan `QUIZ_VALIDATOR_MODEL` `grok-4.3` (keluarga model lain dari generator), `BREAKER_THRESHOLD` (`5`, galat sistemik beruntun sebelum job berhenti cepat dengan pesan layanan model tidak tersedia), `STIMULUS_TYPES` (env `QUIZ_STIMULUS_TYPES`, bawaan `*` = semua jenis), dan batas teknis spesifikasi stimulus (`STIMULUS_MAX_LEAVES`, `STIMULUS_MAX_CHARS`, `STIMULUS_MAX_DEPTH`, `STIMULUS_MAX_SVG_CHARS`, `SVG_MAX_ELEMENTS`).

Nama variabel env di atas generik (tidak berprefiks proyek) — cek tidak bentrok kalau proses ini jalan berdampingan dengan layanan lain di mesin yang sama.

Semua fitur memakai `gpt-5.4-mini` (kecuali validator Quizzer); bedanya di `reasoning_effort`: `none` untuk Annoter (transkripsi rumus/tabel/gambar), `low` untuk fitur yang menalar. Effort `none` pada tugas menalar jatuh akurasinya (validasi soal 4/12 di nano, 9/12 di mini).

## Format prompt

Semua prompt (Annoter, Quizzer, Evaluaizer, Clarifier, dan prompt bersama di `common/`) memakai format baku di bawah ini, dijaga `tests/common/test_prompts_format.py`. Teknik dipilih menurut tugas: contoh few-shot untuk klasifikasi dan format keluaran, kolom alasan singkat sebelum keputusan untuk penilaian, dan daftar periksa sebelum menutup untuk agen. Aturan anti-injeksi ditambahkan otomatis (lihat Pagar prompt).

Prompt Annoter disusun `common/prompt_format.build_prompt(role, task, context, rules, output_format, examples)` dengan heading tetap `# ROLE`, `# TASK`, `# CONTEXT`, `# RULES`, `# OUTPUT FORMAT`, `# EXAMPLES` (bagian kosong dilewati). Pesan user (data) disusun `build_input(**bagian)` dengan heading dari nama argumen (`surrounding_text_not_image_content` menjadi `# SURROUNDING TEXT NOT IMAGE CONTENT`). Teksnya ada di `annoter/prompts.py`.

| Komponen | Teknik | Catatan |
|---|---|---|
| Teks/heading | tanpa LLM | tag dan spasi dibersihkan |
| Rumus | few-shot, 7 contoh | pecahan, geometri, huruf Yunani, tanda kali, tanda baca akhir; kesetiaan 97,1% pada 120 LaTeX unik (v6 lama 83,7%) |
| Tabel | zero-shot, JSON terstruktur | `pengamatan` lalu `deskripsi` |
| Gambar | klasifikasi 3 percobaan, lalu zero-shot per jenis, JSON terstruktur | teks tetangga diberi label "bukan isi gambar" supaya angka dari soal tidak disalin sebagai isi gambar |

Catatan: gambar tidak memakai few-shot karena contoh menjangkar panjang deskripsi. Hasil A/B ada di `docs/research/0002-ab-prompt-annoter.md` dan `0003-klasifikasi-gambar-annoter.md`.

## Modul (annoter/)

**run_mineru.py** — ekstrak satu PDF/rentang halaman lewat `mineru.cli.common.do_parse` in-process (bukan subprocess CLI), simpan `content_list.json` + `.md` + `images/`, hapus file debug. Model MinerU di-cache sebagai singleton dalam proses (`mineru/backend/pipeline/model_init.py`); dipanggil dari worker taskiq (`backend/app/tasks/mineru_tasks.py`, lewat `run_async` yang melaporkan progress), model cuma di-load sekali per proses, bukan per window.
```
uv run python -m annoter.run_mineru --pdf modul.pdf [--out DIR] [--start N] [--end N] \
  [--method auto|txt|ocr] [--no-formula] [--no-table] [--device auto] [--vram N] [--keep-debug]
```

**batch.py** — pecah PDF jadi window sebesar `--max-pages`, jalankan `run_mineru.run` per window ke `<out>/p{awal}-{akhir}/`. Window diproses berurutan.
```
uv run python -m annoter.batch --pdf modul.pdf [--out DIR] [--max-pages 3] \
  [--method auto|txt|ocr] [--no-formula] [--no-table] [--device auto] [--vram N] [--dry-run]
```
`--max-pages 0` = satu run untuk seluruh PDF. `--dry-run` = cetak rencana window tanpa menjalankan MinerU.

**preprocess.py** — `preprocess(content_list_path) -> list[Block]`. Ubah `content_list.json` jadi blok ter-route (`heading`, `text`, `formula`, `table`, `image`). Blok `header`/`footer`/`page_number` dibuang. Teks dengan rumus inline `$...$` dipecah jadi segmen.

**annotate.py** — `annotate_window(content_list_path, breaker=None) -> WindowResult` (blok, jumlah gagal, jumlah berpanggilan LLM); dispatch per rute lewat kamus `ANNOTATORS`, blok berpanggilan LLM yang gagal disimpan kosong berprioritas `high`. `common/resilience.py` berisi `Breaker` (pemutus setelah 5 galat sistemik beruntun, dipakai bersama Quizzer) dan `is_systemic`; `priority.py` berisi aturan `review_priority`; `phrases.py` menyatukan frasa 'tidak terbaca'. Heading dan teks dibersihkan tag/spasi tanpa LLM; rumus, tabel, gambar dikonversi lewat MLLM, paralel sebesar `LLM_MAX_WORKERS`, urutan baca tetap terjaga. Menghitung `review_priority` untuk membantu guru memprioritaskan pengecekan.
```
uv run python -m annoter.annotate content_list.json [annotated.json]
```
Field tiap blok: `block_type`, `reading_order`, `page`, `readable_text`, `review_priority`, `heading_level`, `source_markup`, `caption`, `image_file`, `image_kind`, `ringkasan`, `tabel`. `page` hanya untuk penelusuran, tidak disimpan ke DB. `image_kind` hanya terisi untuk blok gambar (disimpan di `blocks.image_kind`); `ringkasan` dan `tabel` hanya untuk blok tabel (disimpan di `blocks.ringkasan` dan `blocks.tabel`, ADR 0008). `review_priority`: heading dan teks `low`; tabel rusak `high`; gambar `high` bila klasifikasi tidak pasti, deskripsi kosong, atau jenis grafik/diagram/teks_di_gambar, selebihnya `normal`.

**formula.py / table.py / image.py** — konversi per jenis blok lewat MLLM + cache.
- Rumus: `common/formula.py` (`convert_checked`) dipanggil langsung oleh `annotate.py`; verbalisasi LaTeX -> Bahasa Indonesia (model teks).
- `table.py`: tabel -> `TableResult(text, ringkasan, tabel, issues)` (model vision, dari gambar tabel + HTML hasil OCR). Model menghasilkan tabel terstruktur `{judul, kolom, baris}` dan satu kalimat `topik`; bacaan linear (`math_text.table_readable`) dan ringkasan (`math_text.table_summary`) disusun kode dari tabel itu. Sel diverbalisasi (`math_text.spoken_table`). Bila struktur tidak valid, bacaan memakai `deskripsi` dari model dan blok diberi prioritas `high`. `annoter_regenerate.regenerate` mengembalikan `Regenerated(text, ringkasan, tabel, issues)`.
- `image.py`: gambar/grafik -> `ImageAnnotation(kind, text, uncertain)`. `annotate_image` memanggil `classify_image` (tiga percobaan, di-cache per percobaan di namespace `image_kind` dan `image_kind_final`), melewati gambar dekoratif yang yakin, lalu `_describe` dengan prompt per jenis (namespace `image`).

**prompts.py** — seluruh teks prompt Annoter: rumus, tabel, gambar umum, per jenis gambar (`KIND_RULES`), klasifikasi (`image_classifier_*`), dan penentu akhir (`image_arbiter_*`), plus aturan bersama (`NO_OPENER_RULE`, `PLAIN_TEXT_RULE`, `GREEK_RULE`, `FEEDBACK_RULE`). Fungsi `*_system` menyusun system prompt, `*_input` menyusun pesan user.

**common/llm.py** — klien Azure OpenAI (SDK openai, endpoint `/openai/v1/`). `complete_text`, `complete_vision`, `complete_vision_json`, `complete_json`. `complete_vision_json` mengirim gambar dan mengembalikan dict JSON tervalidasi (mengulang sekali dengan pengingat format bila gagal, dan mensyaratkan kunci wajib terisi); `complete_vision` meminta `{"pengamatan": ..., "deskripsi": ...}` (model mencatat apa yang tampak dulu, baru menulis deskripsi) dan mengembalikan `deskripsi`; klasifikasi gambar memakai `complete_vision_json` dengan kunci wajib `jenis`. Batas token dikirim sebagai `max_completion_tokens` dan effort sebagai `reasoning_effort` (rumus/tabel/gambar `none`, quiz dan chatbot `low`). Penolakan filter keamanan Azure (HTTP 400 `content_filter`) diubah jadi `ContentFilterError` (turunan `ValueError`). Gambar dikirim sebagai data URI base64.

**common/cache.py** — cache berbasis file, key = hash(konten, model, `PROMPT_VERSION`). `get(namespace, *parts)` / `put(namespace, value, *parts)`. Tulis atomik. Menghapus `.cache/` membuat panggilan MLLM dihitung ulang.

**annoter_pipeline.py** — orkestrator satu bab, tanpa DB. `run_with_report(outputs_dir) -> RunReport` (dipakai `process_mineru_job_task`; `run` mengembalikan daftar path saja): cari semua `content_list.json` di `outputs_dir`, urutkan per halaman (folder `p{awal}-{akhir}`), annotate tiap window, tulis `annotated.json` di folder window, dan kembalikan daftar path-nya. Penyimpanan ke DB dilakukan backend (`ContentService.ingest_annotated_json`). CLI untuk testing manual:
```
uv run python -m annoter.annoter_pipeline --outputs OUTPUT_DIR/<stem>
```

**annoter_regenerate.py** — titik panggil validasi guru. `regenerate(block_type, feedback, ...)` menghasilkan ulang bacaan satu blok untuk jenis `formula`/`table`/`image` berdasarkan feedback guru. Backend menyimpan hasilnya ke DB — layanan AI tidak menyentuh DB.
```python
regenerate(block_type, feedback, *, source_markup="", image_path=None, caption="", context="")
```

## Modul (quizzer/)

**segment.py** — tanpa LLM. `build_segments(chapter_id, blocks) -> list[Segment]`: potong blok satu bab (urut `reading_order`) menjadi segmen menurut blok dan jumlah karakter, tanpa bergantung pada pola heading. Kelompok tak terpisah (heading ikut blok setelahnya; rumus, tabel, gambar ikut blok teks sebelumnya; penyelesaian ikut contohnya) dikumpulkan sampai `SEGMENT_TARGET_CHARS`, lalu boleh diperpanjang sampai `SEGMENT_MAX_CHARS` hanya untuk berhenti tepat sebelum heading. Tidak pernah memotong di dalam satu blok. Blok di bawah heading pembuka (Tujuan Pembelajaran, Pertanyaan Pemantik, Kata Kunci, Peta Konsep, Pengantar) dibuang. `Segment` membawa `context_text` (overlap `OVERLAP_BLOCKS` blok sebelumnya, hanya konteks baca). `span_text(blocks, start, end)` mengambil teks rentang `reading_order` ditambah margin `SOURCE_MARGIN_BLOCKS`, dibatasi `SOURCE_MAX_CHARS`.

**points.py** — `extract_segment(segment) -> list[dict]`: LLM mengekstrak poin (teks, jenis `definisi`/`rumus`/`prosedur`/`konsep`/`miskonsepsi`/`perbandingan`/`aplikasi`, rentang `reading_order` sumber, kutipan), dinormalisasi kode, di-cache per isi segmen. Keluaran terpotong membagi segmen menjadi dua. `dedupe(points)` membuang poin kembar antar segmen bertetangga lewat kemiripan kata (`POINT_DUPLICATE_SIMILARITY`).

**mapping.py** — `plan_slots(chapters, propose)`: kuota level dihitung kode dari jumlah LOTS/HOTS guru (LOTS ke C1-C3, HOTS ke C4-C5). LLM mengusulkan poin per slot; kode menerima hanya poin yang valid, belum terpakai, dan jenisnya cocok dengan level (`COMPATIBLE_KINDS`), lalu mengisi kekurangan secara deterministik dengan sebaran antar segmen. Poin dipakai ulang hanya bila poin kurang dan dilaporkan.

**generate.py** — `generate_soal(point, source_text, bloom_level, cp_text="", correction="") -> dict`. Satu soal dari satu poin dan teks sumbernya; `correction` berisi daftar masalah untuk regenerasi. Rentang sumber soal diambil dari poin.

**readable.py** — `derive(data)` mengubah keluaran generator (teks berisi `$...$` dan tabel terstruktur) menjadi teks siap-baca plus `markup` soal dan `source_markup` stimulus (tabel disimpan sebagai HTML); `derive_fields` dan `derive_stimulus` dipakai backend saat guru mengedit; `markup_issues` memeriksa LaTeX dan bentuk tabel sebelum diturunkan. Rumus diverbalisasi `common/formula.convert_checked` (pindahan dari Annoter, perilaku sama), tabel dilinearisasi `common/math_text.table_readable` tanpa LLM.

**common/formula.py** — verbalizer rumus gaya kelas (ADR 0007): `convert_checked(latex) -> (bacaan, temuan)` dengan cache (`FORMULA_PROMPT_VERSION`) dan satu kali coba ulang bila `common/formula_check.spoken_issues` menemukan masalah (simbol tersisa, penutup akar/pecahan/pangkat kurang atau berlebih, kurung tidak seimbang atau beruntun, notasi fungsi sederhana dengan kurung). Set uji lintas kategori ada di `common/eval/formula_cases.json` dan `formula_cases_heldout.json`.

**checks.py** — pemeriksaan kode tanpa LLM: struktur opsi A-D, rujukan visual, opsi benar jauh lebih panjang dari opsi lain (`OPTION_LENGTH_RATIO`), stimulus sesuai level, simbol atau rumus mentah, soal yang mengulang stimulus, dan soal yang berakhir menggantung dengan titik-titik.

**shuffle.py** — mengacak urutan opsi dengan target kunci seimbang per bab, memetakan ulang huruf opsi di langkah dan kesimpulan; data yang tidak valid dikembalikan apa adanya.

**validate.py** — `verify_soal(source_text, data, stimulus_text)`: model `QUIZ_VALIDATOR_MODEL` (keluarga berbeda dari generator) menjawab buta (`validate_soal`) dan mengaudit langkah, kesimpulan, opsi lain yang benar, stem ambigu, dan kebutuhan stimulus (`audit_soal`). Tidak pernah melempar; kegagalan infrastruktur tercatat sebagai catatan. Hasilnya hanya menandai soal (tanpa regenerasi); Bloom bukan syarat lolos.

**revise.py / quizzer_regenerate.py** — `compute_regeneration(all_blocks, source_start, source_end, stimulus_source_markup, stimulus_readable, target_soal, sibling_soal, feedback, stimulus_jenis=None, stimulus_spec=None)` (dua argumen terakhir untuk stimulus bertipe: spesifikasi direvisi lewat `revise_stimulus_typed`, divalidasi registry, lalu soal sekelompok di-recheck) dipanggil backend saat guru memberi feedback ke satu soal HOTS: mengedit soal lama (bukan generate dari nol), merevisi stimulus bila perlu, lalu `review_soal` (pemeriksaan kode + verifikasi) menghasilkan daftar masalah untuk tanda review. `review_soal` juga dipanggil backend setelah guru mengedit soal LOTS secara manual.

**stimulus/** — stimulus bertipe (spec 0007, ADR 0012). `registry.py` memetakan nama jenis ke `StimulusKind` (`base.py`: `validate`, `narrate`, `finalize`, `keys`, `raw_keys`, `derived_keys`, `describe`, `available`). Jenis: `tabel` (sel boleh LaTeX; bacaan diturunkan lewat linearisasi tabel bersama), `gambar` (SVG tulisan LLM dan deskripsi; `gambar.py` menolak DOCTYPE, ENTITY, skrip, tautan, `style`, dan `url()` non-lokal, memeriksa daftar putih elemen dan atribut, lalu menulis ulang SVG bersih), `campuran` (komponen berurutan). `registry.check(stimulus)` memeriksa keluaran generator; `registry.derive(stimulus, issues)` menurunkan `readable_text`, `tabel`, `ringkasan`, dan spesifikasi akhir bersama `skema_versi`. `text.py` berisi pembantu bersama. Jenis aktif ditentukan env `QUIZ_STIMULUS_TYPES` (bawaan semua jenis; `teks` saja membatasi ke stimulus teks).

**quizzer_pipeline.py** — `compute_for_quiz(chapters, on_progress=None, seed=None) -> {"items", "report"}`: orkestrasi di atas dengan isolasi kegagalan per slot, anggaran `MAX_GENERATIONS_PER_SLOT` generate per slot, dan paralel sebesar `LLM_MAX_WORKERS`. Dipanggil backend lewat `backend/app/tasks/quiz_tasks.py`.

**prompts.py** — seluruh prompt Quizzer (ekstraksi poin, pemetaan, generate, jawab buta, audit, revisi) berformat seragam lewat `common/prompt_format`.

**common/jsonutil.py** — `parse_json(raw) -> dict`, toleran terhadap code fence markdown dan backslash notasi LaTeX.

## Modul (evaluaizer/)

**evaluate.py** — `evaluate_scratchwork(source_text, stimulus_text, question_text, options, correct_option, correct_langkah, kesimpulan, student_option, student_langkah) -> dict` untuk satu jawaban salah yang punya langkah tertulis siswa (tanpa langkah: `ValueError`, backend tidak memanggilnya): satu panggilan LLM (`EVALUAIZER_MODEL`, effort `EVALUAIZER_EFFORT`) membandingkan langkah siswa dengan langkah kunci dan menghasilkan `dapat_ditentukan`, `langkah_ke` (nomor langkah siswa yang pertama salah, null bila semua langkah benar atau tak dapat ditentukan), `kutipan` (isi langkah itu persis), dan `keterangan` (satu atau dua kalimat netral). Satu putaran perbaikan otomatis bila pemeriksa menemukan masalah; sisa temuan menandai `needs_review`.

**prompts.py** — prompt format seragam dengan satu contoh few-shot; langkah siswa dibungkus `<catatan_pengerjaan_siswa>` dan diperlakukan sebagai data. Cara siswa yang sah dinilai pada caranya sendiri, melompati langkah bukan kesalahan, dan langkah berisi nilai saja dinyatakan tak dapat ditentukan.

**checks.py** — pemeriksaan kode: tipe `dapat_ditentukan`, `langkah_ke` dalam jangkauan, `kutipan` benar-benar ada pada langkah yang ditunjuk, dan `keterangan` tanpa simbol mentah, markdown, huruf bukan Latin, tanda tanya atau seru, kata ganda berurutan, atau istilah internal.

**eval/** — `cases.json` (26 kasus dengan kebenaran dasar `accepted_divergence` dan `dapat_ditentukan`, termasuk kasus langkah berantakan dan 11 skenario penulisan langkah) dan `run_eval.py` (3 ulangan, tanpa model juri): `uv run python -m evaluaizer.eval.run_eval [berkas_keluaran.json]` dari `ai-services/`. Spec [0009](../docs/specs/0009-evaluaizer-letak-kesalahan-dari-langkah-siswa.md), ADR [0013](../docs/adr/0013-evaluaizer-hanya-letak-kesalahan.md) (menggantikan [0009](../docs/adr/0009-evaluaizer-justifikasi-berpoin.md)).

## Alur Pipeline — Clarifier (RAG hibrida)

```
anotasi satu bab selesai (backend/app/tasks/mineru_tasks.py), atau reindex manual oleh guru
  -> reindex (backend/app/tasks/chatbot_tasks.py, taskiq)
       blocks (DB) -> chunk.build_chunks: block dikemas menurut ukuran karakter (target 600, maksimal 1.200,
       overlap satu block); heading hanya titik potong; section ISBN/hak cipta dilewati; tiap chunk juga membawa
       formula_norm (bentuk kanonik semua rumus, dari source_markup) ->
       llm_ext.embed_texts (teks lafal) -> block_embeddings (pgvector + lexical_tsv + formula_norm)
       (siswa baru melihat hasilnya setelah modul dipublikasikan)

siswa mengirim pesan (sesi di-scope ke CLASSROOM, bukan satu chapter; ditolak 400 bila siswa sedang mengerjakan kuis)
  -> bila ada latihan aktif dan pesan hanya satu huruf A-D: balas hasil latihan (kunci, langkah), selesai
  -> agent.run: penyaring peniru instruksi (tanpa LLM) menolak sebelum pencarian
  -> search_module lintas SEMUA chapter published di classroom itu (backend/app/domains/clarifier/sync_search.py)
       tiga daftar kandidat (masing-masing 20 teratas), digabung RRF berbobot (k = 60):
         vektor (cosine, bobot 1,0) | kata kunci (tsvector 'simple', hanya token yang muncul di <= 10% chunk, bobot 0,25)
         | rumus persis (substring formula_norm; hanya bila kueri berumus, bobot 2,0)
       similarity tiap hasil tetap cosine
       -> scope_gate.check_scope memakai similarity TERTINGGI di antara hasil:
            tinggi -> inti, rendah -> di_luar_topik (balasan penolakan, tanpa tool calling lagi),
            zona abu-abu -> LLM classifier (konteks: chunk dengan similarity tertinggi)
       -> retrieval_grader menilai relevansi chunk; chunk peniru instruksi dibuang
  -> tool-calling loop:
       search_module (lagi, kena cache Redis) | search_oer (enam host OER tetap, skor >= 0,6)
       -> compose_answer (WAJIB): rincian sumber (evidence + justifikasi) + ringkasan (+ tabel opsional)
       -> atau request_practice (siswa meminta soal latihan): backend memilih sumber (clarifier.practice),
          membuat soal dengan quizzer_pipeline.generate_practice, menyimpannya di Redis, lalu membalas
          dengan soal tanpa kunci
  -> citations.verify_citations   grounding check: evidence harus match konten tool asli
  -> pemeriksa kebocoran instruksi, lalu simpan ke chat_messages (PostgreSQL) + histori hot di Redis
     (backend/app/domains/clarifier/services.py)
```

Sama seperti quiz: modul `ai-services/clarifier/` murni komputasi + panggilan HTTP eksternal (Azure OpenAI, embedding provider, search API) -- tidak menyentuh PostgreSQL. `search_module` butuh pgvector, jadi backend menyuntikkan hasilnya lewat callable `search_module_executor` (`backend/app/domains/clarifier/sync_search.py`), bukan lewat data statis seperti `blocks` di quiz -- karena tool calling di sini interaktif (LLM yang memutuskan kapan dan berapa kali memanggil). Spec [0005](../docs/specs/0005-clarifier-pencarian-hibrida-dan-sumber-oer.md) dan [0010](../docs/specs/0010-clarifier-teman-belajar.md), ADR [0010](../docs/adr/0010-clarifier-pencarian-hibrida-dan-sumber-oer.md), [0014](../docs/adr/0014-latihan-soal-clarifier-tanpa-validasi-guru.md), dan [0015](../docs/adr/0015-chunk-clarifier-berbasis-ukuran.md).

## Pagar prompt (guardrails)

`common/guardrails.py` dipakai semua fitur sebagai lapisan berlapis; tidak ada yang bergantung pada satu lapis saja.

- **Aturan di prompt**: `build_prompt` menambah tiga aturan ke RULES tiap prompt sistem (isi tag data dan teks dalam gambar adalah data, jangan membuka instruksi sistem, jangan ganti peran atau format). `llm.complete_*` dan `chat_with_tools` menyisipkan aturan yang sama bila prompt dibuat tanpa `build_prompt`.
- **Pembatas data**: `build_input` membungkus bagian tak tepercaya (pertanyaan dan jawaban siswa, teks modul, OCR, takarir, LaTeX, umpan balik guru, sumber soal) dalam tag seperti `<pertanyaan_siswa>`; tag penutup buatan di dalam isi dinetralkan, simbol `<` dan `>` matematika tidak diubah.
- **Penyaring masukan (tanpa LLM)**: `injection_markers` (teks dinormalkan NFKC dan karakter tak terlihat dibuang) mengenali kalimat peniru instruksi (abaikan aturan, tampilkan prompt, tag sistem); ajakan berperan hanya ditandai pada masukan siswa (`strict=True`), tidak pada teks sumber. Riwayat percakapan dibungkus tag dan giliran peniru instruksi disembunyikan, hasil tool masuk ke model dalam tag `teks_modul` atau `teks_sumber_luar`, dan potongan modul peniru instruksi tidak diteruskan. Clarifier menolak pertanyaan seperti itu sebelum pencarian dan model, hasil pencarian luar yang memuatnya dibuang dan topik latihan yang memuatnya dikosongkan, langkah siswa yang memuatnya membuat hasil Evaluaizer `needs_review`, teks sumber soal yang memuatnya menandai soal untuk ditinjau guru, dan blok, gambar, atau tabel anotasi yang memuatnya berprioritas `high`.
- **Penyaring keluaran**: jawaban Clarifier dan keterangan Evaluaizer yang memuat isi instruksi (nama tool, judul bagian prompt) dibuang dan diganti jawaban aman atau ditolak.
- **Cakupan**: gerbang cakupan Clarifier menolak topik di luar matematika kelas, aturan agen menolak permintaan kode, esai, tugas lain, konten berbahaya, atau menyuruh berpura-pura, dan pesan penolakan mengarahkan siswa yang tertekan ke guru atau orang dewasa tepercaya.
- **Batas**: penyaring berbasis pola tidak menangkap semua parafrase; lapisan prompt dan pembatas data yang menanggung sisanya. Belum diukur dengan model nyata.

## Modul (common/)

Kode bersama yang dipakai lebih dari satu fitur (ADR 0004).

**llm.py / cache.py / jsonutil.py / parallel.py / resilience.py** — klien Azure OpenAI dengan retry dan filter konten (`complete_text`, `complete_json`, `complete_vision*`), cache hasil MLLM, parser JSON toleran (termasuk LaTeX), `parallel_map` yang menjaga urutan, dan pemutus sirkuit untuk kegagalan sistemik.

**prompt_format.py / guardrails.py** — `build_prompt` dan `build_input` (format baku, aturan anti-injeksi otomatis, pembatas tag untuk bagian data), serta penyaring peniru instruksi dan pemeriksa kebocoran instruksi (ADR 0016).

**formula.py / formula_check.py / notation_check.py / math_text.py** — verbalizer rumus bersama (`convert_checked`, cache, pemeriksa struktur), pemeriksa bacaan dan sumber rumus, deteksi notasi mentah, serta utilitas teks matematika (pembagi `$...$`, bacaan dan linearisasi tabel, `readable_texts`). Dipakai Annoter, Quizzer, dan Clarifier.

**table_spec.py** — pemeriksa dan narator tabel terstruktur `{judul, kolom, baris}` yang dipakai stimulus Quizzer dan tabel jawaban Clarifier.

**image_prompts.py / image_describe.py / svg_raster.py** — prompt deskripsi gambar dan deskripsi gambar ber-cache lewat model vision (Annoter dan Quizzer), serta rasterisasi SVG ke PNG lewat resvg-py (butuh font; di Docker `fonts-liberation`).

**speakable.py / phrases.py** — pembersih deterministik deskripsi gambar setelah teks model: kutip dibuang, satuan dan pecahan ber-garis miring dibaca 'per', minus, pangkat angka murni, superskrip, panah, dan simbol relasi diganti kata; pola ambigu dibiarkan dan ditandai `description_issues`; elipsis tidak diubah. Dipakai `image.annotate_image` dan `annoter_regenerate`. `phrases.py` memuat frasa 'tidak terbaca' yang dipakai bersama.

## Modul (clarifier/)

**chunk.py** — `build_chunks(chapter_id, blocks) -> list[Chunk]`. Block (heading ikut sebagai block) dikemas menurut ukuran karakter: chunk ditutup di heading berikutnya setelah mencapai `TARGET_CHUNK_CHARS` (600) atau di batas block sebelum `MAX_CHUNK_CHARS` (1.200); heading hanya titik potong pilihan, sehingga section pendek bergabung dan section panjang terpecah. Heading tidak ditinggal sendirian di ujung chunk, chunk terakhir di bawah `MIN_TAIL_CHARS` (250) digabung ke sebelumnya, dan block terakhir chunk (maksimal 300 karakter) diulang di awal chunk berikutnya sebagai overlap. Block pertama tiap chunk selalu unik karena dipakai sebagai `reference` sitasi. Block tunggal di atas batas tidak dipecah. Section metadata penerbit (ISBN, hak cipta) dilewati dan teks sebelum heading pertama menjadi "Pembuka". Setiap chunk menyimpan `formula_norm`. Mengganti chunker mewajibkan reindex semua bab.

**formula_text.py** — `normalize_formula(text)`: bentuk kanonik huruf kecil tanpa spasi untuk LaTeX buku dan rumus ketikan siswa (`\frac{1}{x}` dan `1/x` sama-sama `(1)/(x)`, `x^{2}` dan `x²` sama-sama `x^2`). `formula_spans(question)`: rumus di dalam kalimat pertanyaan (panjang kanonik minimal 5 karakter dan memuat operator). Kecocokan memakai substring persis, bukan trigram, karena `pg_trgm` mengabaikan tanda baca.

**speech.py** — `derive_message(text) -> (bacaan, markup, temuan)`: teks `summary` berisi LaTeX `$...$` dari model diubah menjadi teks bacaan lewat verbalizer bersama (`common/math_text.readable_texts`, gaya ClearSpeak seperti Quizzer); markup LaTeX dikembalikan untuk ditampilkan, kecuali LaTeX tidak valid atau verbalizer melaporkan temuan (markup `None`, tanda dolar dibuang dari bacaan). Spec [0006](../docs/specs/0006-clarifier-rumus-tampil-dan-bacaan.md).

**lexical.py** — `lexical_tokens(question)`: token alfanumerik minimal 3 karakter tanpa kata henti, maksimal 12. **fusion.py** — `reciprocal_rank_fusion(rankings, weights, limit)`.

**llm_ext.py** — `chat_with_tools` (tool calling lewat Azure OpenAI, reuse client `common/llm.py`); `embed_texts`/`embed_text` kini ada di `common/embedding.py` (batch 16 teks dikirim paralel, lihat `EMBEDDING_*` di `common/config.py`) dan diekspor ulang di sini.

**tools.py** — skema tool (format OpenAI function calling): `search_module`, `search_oer`, `compose_answer`.

**external_tools.py** — `search_oer(query)`: pencarian lewat search API (Tavily) dengan `include_domains` = enam host di `trusted_domains.OER_HOSTS`, lalu hasil di luar daftar atau berskor di bawah `OER_MIN_SCORE` (0,6) dibuang di kode; hasil kosong mengembalikan catatan "tidak ada sumber tepercaya". Tanpa parameter topik tambahan: menempelkan "matematika" ke kueri menurunkan skor (0,75 menjadi 0,34 pada satu kueri uji).

**trusted_domains.py** — `OER_HOSTS`: `murid.kemendikdasmen.go.id`, `repositori.kemendikdasmen.go.id` (PDF modul resmi Kemendikdasmen; cuplikan 2.000 sampai 2.400 karakter, karakter font simbol dibuang dan rumus sering terpotong), `openstax.org`, `www/id/en.khanacademy.org` (host persis; subdomain lain seperti `zh.khanacademy.org` tidak lolos), dan `is_trusted(url)`. Tanpa tier.

**scope_gate.py** — `check_scope(question, top_chunks)`: similarity tertinggi di antara hasil retrieval (bukan elemen pertama) untuk kasus jelas, LLM classifier (structured JSON, konteks dari chunk dengan similarity tertinggi) untuk zona abu-abu. Klasifikasi: `inti`/`perluasan`/`campuran`/`di_luar_topik`.

**citations.py** — `verify_citations(sources, tool_outputs)`: grounding check fuzzy-match evidence yang diklaim LLM ke konten mentah tool result (supaya kutipan tidak dikarang). URL OER yang tertukar satu-dua karakter saat disalin model dipetakan ke URL hasil tool yang nyaris sama (kemiripan >= 0,97) dan `reference` dikoreksi ke URL itu.

**table.py** — `build(spec, grounding_texts)`: tabel terstruktur opsional dari `compose_answer`; divalidasi lewat `common/table_spec` (bersama stimulus Quizzer) dan angkanya harus muncul di sumber atau ringkasan; tidak valid berarti `tabel` None plus temuan. Spec [0010](../docs/specs/0010-clarifier-teman-belajar.md) tahap 2.

**practice.py** — latihan soal buatan AI di antarmuka chat: `select_source(topic, executor)` memilih bagian modul relevan sebagai sumber, `stored_form` bentuk simpan, `parse_choice` mengenali pesan berisi satu huruf pilihan, `question_reply` dan `answer_reply` menyusun pesan chat (soal tanpa kunci, lalu hasil dengan kunci dan langkah). Soalnya dibuat `quizzer_pipeline.generate_practice` (generate, pemeriksa kode, jawab buta, dan audit yang sama dengan Quizzer; lolos hanya tanpa temuan apa pun, satu perbaikan, selain itu ditolak). Model hanya memanggil tool `request_practice`; backend yang merangkai semuanya dan menyimpan latihan di Redis, bukan DB. ADR [0014](../docs/adr/0014-latihan-soal-clarifier-tanpa-validasi-guru.md), spec [0010](../docs/specs/0010-clarifier-teman-belajar.md).

**retrieval_grader.py** — `grade_chunks` (LLM menilai relevansi chunk), `safe_chunks` (membuang chunk peniru instruksi), dan `evaluate` (chunk relevan plus teks hasil tool).

**agent.py** — `run(question, history, search_module_executor) -> dict`. Orkestrator: search_module dulu buat scope gate -> tool-calling loop -> `compose_answer` -> verifikasi kutipan. Dipanggil backend (`backend/app/domains/clarifier/services.py`) lewat `asyncio.to_thread`.

**eval/** — `dataset.json` (17 pertanyaan dengan heading sumber), `formula_queries.json` (14 pertanyaan rumus persis dengan blok sumber, ditambah 2 kontrol negatif), `blocks/bab1.json` dan `bab2.json`. Evaluasi retrieval membaca database sehingga pelaksananya skrip sesi, bukan modul `ai-services/`; hasilnya di ADR 0010.
