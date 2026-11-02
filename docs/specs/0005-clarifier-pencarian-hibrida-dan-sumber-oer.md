# 0005. Clarifier: pencarian hibrida dan sumber OER saja

- Status: selesai
- Tanggal: 2026-10-28
- ADR terkait: [0010](../adr/0010-clarifier-pencarian-hibrida-dan-sumber-oer.md); dasar: [riset 0001](../research/0001-filter-sumber-web-clarifier.md)

## Masalah

Siswa tunanetra bertanya pada Clarifier tentang isi modul, dan sebagian pertanyaan memuat rumus atau persamaan yang harus cocok persis. Ada tiga masalah.

- **Rumus tidak ditemukan.** Pencarian hanya memakai kemiripan vektor (cosine) pada teks lafal (`readable_text`). Rumus di chunk hanya berupa kata ("x kuadrat dikurangi lima x ..."), LaTeX aslinya (`blocks.source_markup`) tidak ikut diindeks, dan tidak ada pencarian kata kunci. Pertanyaan yang menyalin persamaan persis sering meleset ke chunk yang sekadar mirip topik.
- **Sumber luar tidak tepercaya.** `search_academic_web` meloloskan sumber tier 3 (bucket S3, blog, PDF dosen) ke jawaban siswa dengan sitasi tetap berstatus `verified` (F-014). Wolfram Alpha hanya memberi satu baris hasil tanpa penjelasan. Riset 0001 memutuskan sumber luar dibatasi pada daftar datar domain OER dengan ambang skor relevansi 0,7, tanpa tier, tanpa Wolfram, dan tanpa `search_academic_web`.
- **Cacat kecil di sekitar retrieval.** Halaman hak cipta ikut di-embed dan chunk bisa sampai 5.353 karakter tanpa batas (F-008); kunci cache retrieval tidak memuat `top_k` (C-003); `scope_gate` membaca `top_chunks[0]["similarity"]` sehingga salah bila urutan hasil berubah (C-004); migrasi tidak membuat ekstensi `vector` (F-003).

## Perilaku yang diharapkan

Pencarian modul:

1. Pertanyaan yang memuat rumus atau persamaan (diketik sebagai teks, misalnya `x^2 - 5x + 6 = 0` atau `2x+3=11`) menemukan chunk yang memuat rumus itu, walau kata-kata di sekitarnya berbeda dari modul.
2. Pertanyaan tanpa rumus tetap menemukan chunk yang relevan secara makna, tidak lebih buruk daripada sekarang.
3. Pertanyaan yang memakai kata-kata persis dari modul (istilah, nama teorema) menemukan chunk yang memuat kata itu walau vektornya kurang mirip.
4. Hasil pencarian modul tetap membawa `similarity` (cosine) per chunk; `scope_gate` memakai nilai tertinggi di antara hasil, bukan elemen pertama.
5. Halaman hak cipta, ISBN, dan metadata penerbit tidak diindeks; chunk yang lebih panjang dari batas dipecah di batas blok sehingga rumus tidak terpotong.

Sumber luar:

6. Tool luar hanya `search_oer`. Ia mencari di daftar datar domain: `murid.kemendikdasmen.go.id`, `repositori.kemendikdasmen.go.id`, `openstax.org`, `www.khanacademy.org`, `id.khanacademy.org`, `en.khanacademy.org` (hanya https). Subdomain lain (misalnya `zh.khanacademy.org`) tidak lolos.
7. Hasil dengan skor di bawah 0,6 (`OER_MIN_SCORE`; semula 0,7, diturunkan atas keputusan user setelah F-049) dibuang. Bila tidak ada yang tersisa, tool mengembalikan "tidak ada di sumber tepercaya" dan model menjawab bahwa sumber luar tidak ditemukan, tanpa mengarang.
8. `query_wolfram_alpha`, `search_academic_web`, dan tier kepercayaan (`trust_tier`) dihapus. Tangga eskalasi: `search_module`, lalu `search_oer`, lalu `compose_answer`.
9. Aturan lain tidak berubah: jawaban hanya dari hasil tool, kutipan diverifikasi terhadap isi tool, sitasi yang gagal verifikasi tetap diberi label, ringkasan 2 sampai 3 kalimat tanpa markdown, pertanyaan majemuk dan sejarah konsep seperti sekarang.

## Di luar cakupan

- UI Flutter dan tampilan sitasi.
- Reranker model terpisah, ganti model embedding, atau chunking berbasis semantik.
- Mengubah ambang `scope_gate` (`SCOPE_SIM_HIGH`, `SCOPE_SIM_LOW`) selain memeriksa bahwa klasifikasinya tidak memburuk.
- Menulis ulang notebook RAGAS.
- Tambahan domain OER selain enam host (CK-12, LibreTexts, dan lainnya ditolak sementara; ditambah bila uji topik lain menunjukkan celah). `repositori.kemendikdasmen.go.id` ditambahkan kemudian atas keputusan user setelah pengukuran di ADR 0010.
- Rumus yang diucapkan sebagai kata ("x kuadrat") tidak diubah menjadi bentuk simbol; ia dilayani oleh vektor dan pencarian kata kunci pada teks lafal.

## Perubahan data

Satu migrasi Alembic pada `block_embeddings`:

- `CREATE EXTENSION IF NOT EXISTS vector` dan `pg_trgm` ditambahkan di migrasi pertama (`7687613b2cdc`), tempat tipe `Vector` dan indeks `gin_trgm_ops` judul modul pertama dipakai (F-003); migrasi hibrida sendiri tidak membuat ekstensi.
- `lexical_tsv` tsvector, kolom generated dari `chunk_text` dengan konfigurasi `simple` (tidak ada stemmer Indonesia bawaan), indeks GIN.
- `formula_norm` Text not null default `''`: bentuk kanonik semua rumus chunk, dipisah `;`.

Kolom baru nullable atau berdefault sehingga baris lama tetap valid; semua bab perlu reindex (tidak ada migrasi data otomatis, reindex memanggil API embedding dan menulis `block_embeddings`). Teks yang di-embed tidak berubah. Migrasi dan reindex hanya dijalankan di DB dev setelah persetujuan user; produksi mengikuti runbook deploy.

## Perubahan API

Tidak ada endpoint atau jalur baru. Perubahan respons `POST /clarifier/sessions/{id}/messages` dan riwayat pesan:

- `sources[].trust_tier` dihapus (tidak ada tier lagi). Pesan lama di DB yang masih memuat field itu tetap terbaca; field tak dikenal diabaikan.
- `sources[].source_type` hanya `modul` atau `oer` untuk jawaban baru; pesan lama bisa berisi `wolfram_alpha` atau `web`.

Frontend belum dimulai sehingga tidak ada konsumen yang rusak. Koleksi Postman disinkronkan lewat `api-contract-sync` dengan persetujuan user.

## Perubahan AI

- `clarifier/formula_text.py` (baru): `normalize_latex` membuang `\left`, `\right`, `\textstyle`, `\displaystyle` dan spasi, mengubah `\times` dan `\cdot` menjadi `*`, `\frac{a}{b}` menjadi `(a)/(b)`, dan melepas kurung kurawal pangkat; `normalize_plain_math` membawa rumus yang diketik siswa ke bentuk kanonik yang sama; `formula_spans` mengambil rumus dari kueri (panjang kanonik minimal 5 karakter agar `x=2` tidak cocok ke mana-mana). Kecocokan rumus memakai substring persis, bukan trigram: `pg_trgm` mengabaikan tanda baca sehingga `x^2-5x+6` dan `x^2+5x+6` tidak terbedakan, padahal yang diminta cocok persis.
- `clarifier/lexical.py` dan `clarifier/fusion.py` (baru): pembentuk tsquery dari kueri tanpa kata henti, dan fungsi RRF murni.
- `chunk.py`: menerima `source_markup`; mengumpulkan LaTeX tiap chunk (blok formula dan potongan `$...$` di blok teks) menjadi `formula_norm`; membentuk `lexical_text`; melewati chunk metadata dan memecah chunk di atas batas panjang (awal: 1.500 karakter) di batas blok.
- `sync_search.py` (backend): tiga daftar kandidat, masing-masing 20 teratas: kosinus vektor; leksikal `ts_rank_cd` dengan tsquery OR dari token kueri (tanpa kata henti); kecocokan rumus persis, yaitu chunk yang `formula_norm`-nya memuat bentuk kanonik rumus di kueri (urut: jumlah rumus kueri yang cocok, lalu `formula_norm` terpendek), hanya bila kueri berumus. Digabung dengan Reciprocal Rank Fusion (k = 60), diambil `top_k`. `similarity` tiap hasil tetap cosine dan dihitung untuk semua kandidat. Filter kelas dan modul publish tetap. Kunci cache retrieval memuat mode, `top_k`, dan versi skema pencarian (C-003). `reference` tetap `block_ids[0]` agar `citations` tidak berubah.
- `scope_gate.py`: memakai nilai `similarity` tertinggi (C-004).
- `external_tools.py`: hanya `search_oer`: `include_domains` = enam host (batas ditegakkan lagi di kode), `search_depth` advanced, `max_results` 5, penyaringan host di kode, skor minimum 0,6 (`OER_MIN_SCORE`). Catatan error disanitasi seperti sekarang (F-016).
- `trusted_domains.py`: daftar datar enam host dan fungsi pemeriksa host; tier dihapus. `tools.py`, `agent.py` (prompt, `_dispatch`, pesan fallback), `citations.py`, `retrieval_grader.py` (catatan yang menyebut tool lama), `config.py` (`WOLFRAM_*`), `.env.example` disesuaikan.
- Prompt: format seragam dipertahankan; yang diubah hanya bagian tool, eskalasi, dan kepercayaan sumber. Model dan effort tidak berubah. `PROMPT_VERSION` tidak berlaku (bukan prompt anotasi).
- Biaya: embedding kecil untuk reindex satu atau dua bab dan uji; sekitar 24 kredit pencarian Tavily untuk uji cakupan sumber luar.

## Aksesibilitas

- Jawaban dibacakan pembaca layar: ringkasan tetap 2 sampai 3 kalimat tanpa markdown dan simbol mentah. Kutipan (`evidence`) dari Khan Academy atau OpenStax berbahasa Inggris bisa terbaca dengan suara bahasa lain di TalkBack; ringkasan tetap berbahasa Indonesia. Catatan ini diteruskan ke desain frontend.
- Menghapus tier menghilangkan label "sumber belum terverifikasi" tier 3 dari ringkasan; digantikan oleh pembatasan sumber, bukan oleh peringatan.
- Pencarian modul memakai teks lafal sebagai konten yang dikembalikan ke model, jadi rumus yang sampai ke siswa tetap berupa kata.

## Verifikasi

Perilaku nyata, bukan hanya kode:

1. Migrasi di DB dev: upgrade, downgrade, upgrade; `\d block_embeddings` menunjukkan kolom dan indeks baru; ekstensi `vector` ada.
2. Tes unit (skrip scratchpad; `pytest` menunggu persetujuan user): `normalize_latex` dan `normalize_plain_math` pada pasangan LaTeX dan teks ketikan, termasuk spasi gaya OCR (`2 0 . 0 0 0`), `formula_spans`, pembentuk tsquery, `build_chunks` (chunk metadata dilewati, pemecahan, `formula_norm`), penggabungan RRF, kunci cache.
3. Evaluasi retrieval: recall@5 dan MRR untuk vektor saja dan hibrida, pada `dataset.json` (17 pertanyaan) ditambah paling sedikit 10 pertanyaan rumus-persis yang saya susun dari blok bab 1 dan 2 dan Anda setujui sebelum dipakai (disimpan di `clarifier/eval/formula_queries.json`). Pelaksananya skrip sesi di luar repo karena membaca database (aturan keras 1: `ai-services/` tidak menyentuh DB); kasus dan hasilnya yang masuk repo. Blok eval dimuat ke bab uji baru di DB dev lalu di-reindex. Kriteria: recall@5 hibrida tidak di bawah vektor saja pada seluruh set, dan lebih tinggi pada pertanyaan rumus-persis; bila tidak, desain ditinjau ulang. Tiga ulangan untuk bagian yang memanggil LLM; hasil dicek ke sumber (isi chunk), bukan hanya skor.
4. `scope_gate`: klasifikasi 17 pertanyaan dataset sama atau lebih baik dibanding vektor saja; tidak ada pertanyaan inti yang menjadi `di_luar_topik`.
5. Sumber luar: 10 pertanyaan perluasan dan 2 pertanyaan di luar OER; semua hasil berasal dari enam host, skor ≥ 0,6; pertanyaan tanpa hasil memicu jawaban "tidak ditemukan"; laporkan berapa hasil relevan yang terbuang pada ambang 0,6 (dapat diturunkan atas keputusan user). Baca isi minimal 5 hasil `murid.kemendikdasmen.go.id` untuk memastikan teksnya cukup bagi pembaca layar (belum diverifikasi di riset).
6. Alur nyata melalui API dan worker dev: reindex bab (task taskiq), buat sesi, tanya isi modul, tanya rumus persis, tanya di luar topik, tanya perluasan; periksa `sources`, `scope_klass`, dan `tool_calls`.
7. Tinjauan `lydera-reviewer` dan `a11y-reviewer`; sinkron Postman; catat temuan di `docs/planning/findings.md` dan tutup F-003, F-008, F-014, C-003, C-004 bila terbukti.
