# AI Services

Komputasi murni: tidak ada modul di sini yang menyentuh database. Backend membaca blok dari DB, memanggil fungsi di sini, lalu menyimpan hasilnya.

## Fitur

- `common/`: `config` (Azure, model dan effort bersama, `PROMPT_VERSION`), `llm`, `cache`, `jsonutil`, `parallel`, `prompt_format`, `embedding`, `formula` (verbalizer rumus gaya kelas dan prompt-nya), `formula_check` (pemeriksa struktur bacaan rumus), `math_text` (LaTeX inline, tabel, validasi), `eval/` (set uji rumus).
- `annoter/`: `run_mineru` (layout), `batch` (window halaman), `preprocess`, `annotate` (orkestrasi window dan dispatch per rute), `priority` (aturan `review_priority`), `resilience` (pemutus rangkaian untuk outage LLM), `phrases` (frasa 'tidak terbaca'), `speakable` (pembersih deskripsi gambar dan tabel), `table`, `image`, `prompts`, `annoter_pipeline`, `annoter_regenerate`, `config`. Rumus memakai `common/formula` langsung.
- `quizzer/`: `segment`, `points`, `mapping`, `generate`, `checks`, `shuffle`, `validate`, `revise`, `readable`, `prompts`, `quizzer_pipeline`, `quizzer_regenerate`, `config`, `eval/`.
- `evaluaizer/`: `evaluate`, `prompts`, `checks`, `config`, `eval/`.
- `clarifier/`: `agent`, `tools`, `scope_gate`, `retrieval_grader`, `citations`, `chunk`, `formula_text`, `lexical`, `fusion`, `speech`, `external_tools`, `llm_ext`, `trusted_domains`, `config`, `eval/`.

Impor berbasis paket (`from common import llm`, `from annoter import prompts`). `ai-services/` harus ada di `sys.path` (backend lewat `app/utils/paths.py`, Dockerfile lewat `PYTHONPATH`). CLI dijalankan dari `ai-services/` sebagai `uv run python -m annoter.annotate ...`.

## Konfigurasi model

Azure OpenAI endpoint `/openai/v1/`; `.env` hanya dibaca saat runtime. Default bersama ada di `common/config.py`, model per fitur di `<fitur>/config.py`. Semua fitur memakai `gpt-5.4-mini`: Annoter effort `none`, Quizzer, Evaluaizer, dan Clarifier effort `low` (effort `none` menurunkan akurasi tugas menalar). Satu pengecualian: validator Quizzer `grok-4.3` (keluarga model berbeda dari generator). Embedding `text-embedding-3-large`, 3072 dimensi. Filter jailbreak Azure mengembalikan HTTP 400 `content_filter`, dipetakan ke `ContentFilterError`.

## Aturan

- Ubah prompt atau model Annoter (`annoter/prompts.py`, `annoter/table.py`, `annoter/image.py`) berarti naikkan `PROMPT_VERSION` (prompt rumus di `common/formula.py` memakai `FORMULA_PROMPT_VERSION`) di `common/config.py`; kunci cache memuatnya. Cache ada di `ai-services/.cache`, output MinerU di `annoter/output` (keduanya gitignored).
- Format prompt seragam lewat `common/prompt_format.build_prompt` dengan heading `# ROLE`, `# TASK`, `# CONTEXT`, `# RULES`, `# OUTPUT FORMAT`, `# EXAMPLES`; pesan user lewat `build_input`. Teks prompt Annoter hanya ada di `annoter/prompts.py`.
- Teknik Annoter per komponen: rumus few-shot (7 contoh), tabel dan gambar zero-shot dengan keluaran JSON terstruktur (`pengamatan` lalu `deskripsi`). Few-shot untuk gambar sengaja dihindari: contoh menjangkar panjang deskripsi sehingga detail berkurang.
- Prompt gambar: larang kalimat pembuka dan markdown, ringkas tanpa enumerasi tiap titik grafik, dan ikuti gambar, bukan teks konteks (konteks diberi label "bukan isi gambar").
- Gambar diklasifikasi tiga kali (tanpa konteks, dengan teks tetangga maksimal 400 karakter, lalu penentu akhir) ke `dekoratif`, `ilustrasi_konteks`, `geometri`, `grafik`, `diagram`, `teks_di_gambar`. Dekoratif dengan keyakinan 4 atau lebih dilewati (teks kosong); jenis lain memakai prompt per jenis; klasifikasi ragu jatuh ke `ilustrasi_konteks` berprioritas review tinggi. Jenisnya keluar sebagai `image_kind` di `annotated.json`. Dasar keputusan: `docs/research/0003-klasifikasi-gambar-annoter.md`.
- `review_priority`: heading dan teks `low`; tabel rusak (sel kosong lebih dari 30% atau karakter rusak) `high`; gambar `high` bila klasifikasi tidak pasti, deskripsi kosong, atau jenis grafik/diagram/teks_di_gambar; selebihnya `normal`.
- Tabel (ADR 0008, spec 0003): Annoter menghasilkan `tabel` terstruktur dan `topik` dari model; `tabel` yang dibacakan, bacaan linear, dan ringkasan disusun kode (`math_text.spoken_table`, `table_readable`, `table_summary`); Quizzer membuatnya semua oleh kode untuk stimulus. Ubah prompt tabel berarti naikkan `TABLE_PROMPT_VERSION` (bukan `PROMPT_VERSION`).
- Bacaan rumus (ADR 0007): aturan gaya kelas ('f dari g dari empat', penutup 'selesai akar/pecahan/pangkat', 'kurung kedua') di `common/formula.py`; `convert_checked` memeriksa hasil dengan `formula_check.spoken_issues` dan mencoba ulang sekali; yang masih bermasalah ditandai `review_priority` tinggi. Cache rumus memakai `FORMULA_PROMPT_VERSION`, bukan `PROMPT_VERSION`. Ubah prompt rumus berarti naikkan `FORMULA_PROMPT_VERSION` dan jalankan ulang evaluasi pada `common/eval/formula_cases*.json`.
- Saklar `QUIZ_MARKUP_ENABLED=1` (bawaan mati) mengaktifkan soal Quizzer dengan LaTeX dan tabel; mati berarti soal ditulis dengan kata.
- Quizzer menulis rumus sebagai LaTeX inline `$...$` dan tabel terstruktur (spec 0002 Fase A). `quizzer/readable.py` menurunkan teks siap-baca (rumus lewat `common/formula.convert_checked`, tabel dilinearisasi kode); markup disimpan di `soal.markup` dan `soal_stimulus.source_markup`, teks siap-baca di kolom teks biasa. Verifikasi dan pemeriksaan kode bekerja pada teks siap-baca. `common/jsonutil.parse_json` melindungi backslash LaTeX di JSON keluaran LLM.
- Quizzer (spec 0001): segmen dipotong menurut blok dan karakter; LLM mengekstrak poin dan mengusulkan pemetaan, kode menegakkan kuota guru dan level Bloom; verifikasi validator lintas keluarga memeriksa jawaban dan justifikasi; satu slot gagal tidak membatalkan job. Cache Quizzer memakai `QUIZ_PROMPT_VERSION` (`quizzer/config.py`), bukan `PROMPT_VERSION`.
- Bagian teks/heading dari modul tidak lewat LLM (verbatim). Rumus, tabel, gambar lewat LLM.
- Nilai env kosong harus jatuh ke default: pakai `os.getenv(name) or default`.
- MinerU di mesin dev: VRAM kecil, pakai window kecil (`batch --max-pages 3` untuk formula + tabel).
- Eval model: lihat skill `/model-eval`.
