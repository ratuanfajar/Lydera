# Chatbot (RAG) — Cara Kerja Lengkap

Chatbot tanya-jawab materi untuk siswa, berbasis RAG (Retrieval-Augmented Generation) + tool calling ke sumber eksternal. Fiturnya kebagi di 2 tempat, dan dokumen ini menyambungkan keduanya:

- **`ai-services/chatbot/`** — murni komputasi + panggilan HTTP eksternal (OpenRouter, Wolfram, Tavily). **Tidak menyentuh PostgreSQL/Redis sama sekali.**
- **`backend/app/domains/chatbot/`** — semua yang menyentuh database (baca `blocks`, tulis `block_embeddings`, CRUD sesi/pesan) dan orkestrasi (endpoint HTTP, task async, cache Redis).

Aturan ini bukan kebetulan — diikuti dari pola yang sama persis dipakai fitur `annotation`/`quiz` yang sudah ada duluan (lihat [CONTRACT.md](../../CONTRACT.md)).

---

## Bagian 1 — Dari PDF sampai jadi Vector (Indexing)

### 1.1 Titik mula: guru upload PDF

```
POST /api/chapters   (multipart form-data: module_id, title, cp_id, file=PDF)
```

Ini **bukan** bagian dari chatbot — ini pipeline `annotation` yang sudah ada duluan. Tapi chatbot menempel di ujungnya. Alurnya (`backend/app/tasks/mineru_tasks.py`):

```
1. MinerU ekstrak PDF -> content_list.json (layout per halaman)
2. annotate.py: rumus/tabel/gambar -> MLLM -> teks siap-dibaca (readable_text)
3. Simpan ke tabel `blocks` (readable_text, block_type, reading_order, chapter_id)
4. status job = "done"
5. >>> TRIGGER OTOMATIS CHATBOT <<<  (baris baru yang menyambungkan ke bagian 2)
   await reindex_chapter_task.kiq(chapter_id=chapter_id)
```

Baris ke-5 itu titik sambung persisnya — begitu block tersimpan, task reindex chatbot langsung di-enqueue ke taskiq, **tanpa** guru perlu klik apapun lagi.

### 1.2 Reindex: block → chunk → vector

Task `reindex_chapter_task` (`backend/app/tasks/chatbot_tasks.py`) memanggil `ChatbotService.reindex_chapter()` (`backend/app/domains/chatbot/services.py`):

```python
# backend/services.py (ambil dari DB)
blocks = await self.repo.get_blocks_for_chapter(chapter_id)   # SELECT * FROM blocks WHERE chapter_id=...

# ai-services (murni komputasi, tidak sentuh DB)
chunks = chatbot_chunk.build_chunks(chapter_id, blocks_as_rows)   # chunk.py
embeddings = llm_ext.embed_texts([c.text for c in chunks])        # llm_ext.py, panggil OpenRouter

# backend (tulis ke DB)
kb = await self.repo.bump_chapter_kb_version(chapter_id)          # kolom kb_version += 1
await self.repo.replace_block_embeddings(chapter_id, kb.kb_version, [...])  # INSERT ke block_embeddings
```

**Chunking (`chunk.py`)** — SATU block DB = SATU chunk/vector. Tidak digabung, tidak dibedakan cara prosesnya per `block_type` (heading/text/formula/table/image semua diperlakukan sama — karena sudah diverbalisasi jadi teks biasa di tahap annotation). Satu-satunya "olahan": block non-heading dikasih prefix heading terdekat sebagai konteks.

```python
# Contoh isi tabel `blocks`:
#  id=85, block_type='heading', readable_text='A. Barisan Aritmetika'
#  id=86, block_type='text',    readable_text='Barisan aritmatika adalah...'
#
# Hasil chunk.build_chunks():
#  Chunk(block_ids=[85], heading='A. Barisan Aritmetika', text='A. Barisan Aritmetika')
#  Chunk(block_ids=[86], heading='A. Barisan Aritmetika', text='A. Barisan Aritmetika: Barisan aritmatika adalah...')
```

**Embedding (`llm_ext.py`)** — tiap `chunk.text` dikirim ke OpenRouter `/embeddings` (model `EMBEDDING_MODEL`, default `openai/text-embedding-3-large`, 3072 dimensi), balik jadi array 3072 angka float.

**Simpan (`backend/repository.py`)** — satu baris per chunk ke tabel `block_embeddings`:

| Kolom | Isi |
|---|---|
| `chapter_id` | Bab asal |
| `block_ids` | `[85]` (array, isinya cuma 1 elemen karena 1 chunk = 1 block) |
| `heading` | Konteks heading terdekat |
| `chunk_text` | Teks yang di-embed |
| `embedding` | `vector(3072)` — pgvector |
| `kb_version` | Versi reindex ke berapa |

Reindex penuh (bukan incremental) — tiap kali dipanggil, semua `block_embeddings` lama untuk chapter itu **dihapus** lalu ditulis ulang (`DELETE ... WHERE chapter_id = ...` lalu `INSERT` baru). Alasan: volume per bab kecil, diff itu lebih rumit daripada gunanya.

### 1.3 Reindex manual (opsional, kalau perlu ulang)

```
POST /api/chatbot/chapters/{chapter_id}/reindex        -- satu bab
POST /api/chatbot/classrooms/{classroom_id}/reindex     -- SEMUA bab published di satu kelas sekaligus
```

Dipakai kalau: guru edit/regenerate isi block setelah upload awal (belum ada auto-trigger untuk kasus ini), atau ganti `EMBEDDING_MODEL`/`EMBEDDING_DIM` (wajib reindex ulang SEMUA bab, dimensi vector lama tidak kompatibel).

---

## Bagian 2 — Dari Pertanyaan Siswa sampai Jawaban (Retrieval + Tool Calling)

### 2.1 Sesi chat di-scope ke CLASSROOM, bukan ke satu chapter

```
POST /api/chatbot/sessions   body: {"classroom_id": 7}
```

Kenapa classroom, bukan chapter: siswa boleh nanya lintas semua bab yang sudah dipelajari di kelas itu, tanpa perlu bilang "cari di bab mana" — pencarian vector yang otomatis nemuin bab paling relevan (lihat 2.3). `validate_student_classroom_access` mengecek siswa memang terdaftar (`student_classrooms`) sebelum sesi dibuat.

### 2.2 Siswa kirim pertanyaan

```
POST /api/chatbot/sessions/{session_id}/messages   body: {"question": "apa itu barisan aritmatika?"}
```

Router (`backend/router.py`) → `ChatbotService.ask()` (`backend/services.py`):

```python
history = await self._get_history(session_id)   # Redis dulu, fallback Postgres kalau kosong
search_module_executor = make_search_module_executor(session.classroom_id, TOP_K_CHUNKS)
result = await asyncio.to_thread(chatbot_agent.run, question, history, search_module_executor)
```

`asyncio.to_thread` — karena `agent.run()` itu fungsi **sinkron** (loop tool-calling, panggil LLM berkali-kali, blocking), dijalankan di thread terpisah supaya tidak macetin event loop FastAPI.

`search_module_executor` — **callable**, bukan data statis. Ini titik sambung DB↔AI-services: backend yang punya akses pgvector, `ai-services/agent.py` cuma dikasih "tombol" buat manggil pencarian itu tanpa tahu detail SQL-nya.

### 2.3 Retrieval: pgvector query lintas semua bab di classroom

`backend/sync_search.py`, fungsi `search_similar_chunks_cached`:

```sql
SELECT be.id, be.block_ids, be.heading, be.chunk_text, be.chapter_id,
       1 - (be.embedding <=> $1) AS similarity     -- $1 = vector pertanyaan
FROM block_embeddings be
JOIN chapters c ON c.id = be.chapter_id
JOIN modules m ON m.id = c.module_id
WHERE m.classroom_id = $2 AND lower(m.status::text) = 'publish'
ORDER BY be.embedding <=> $1
LIMIT $3                                            -- TOP_K_CHUNKS, default 5
```

- `<=>` adalah operator cosine distance pgvector; `similarity = 1 - distance`.
- Filter `classroom_id` + `status = 'publish'` — inilah yang bikin pencarian otomatis lintas SEMUA bab yang sudah direindex di kelas itu, dan otomatis **tidak** bocor ke bab yang belum di-publish guru.
- Pencarian **tidak pakai index ANN** (HNSW/IVFFlat) — `text-embedding-3-large` (3072 dim) melebihi batas 2000 dim yang didukung pgvector untuk index itu. Tidak masalah: query sudah di-scope ke satu classroom dulu, jadi corpus per query cuma puluhan-ratusan baris — brute-force exact scan masih cepat.
- Query jalan lewat `psycopg` (sync), **bukan** `AsyncSession` SQLAlchemy — karena dipanggil dari dalam thread terpisah (lihat 2.2), tidak bisa pinjam session yang terikat event loop request asal.

**2 lapis cache Redis** (di file yang sama):

| Cache | Key | TTL |
|---|---|---|
| Query embedding | `chatbot:emb:{hash(text+model)}` | 7 hari |
| Hasil retrieval | `chatbot:retr:{classroom_id}:{hash(query)}` | 1 jam |

### 2.4 Scope gate — cegah pertanyaan di luar materi

`ai-services/scope_gate.py`, dipanggil di awal `agent.run()`:

```python
top_chunks = search_module_executor(question)      # panggilan retrieval PERTAMA
scope = scope_gate.check_scope(question, top_chunks)
```

Skor `similarity` chunk top-1 **langsung** jadi sinyal:

```
similarity >= SCOPE_SIM_HIGH (default 0.32)  -> "inti", lanjut
similarity <= SCOPE_SIM_LOW  (default 0.12)  -> "di_luar_topik", TOLAK, stop di sini
di antaranya                                 -> LLM classifier (pakai isi chunk top-1 sebagai
                                                 konteks, bukan deskripsi statis) -> inti/perluasan/di_luar_topik
```

Kalau `di_luar_topik`: langsung balas pesan redirect, **tidak ada tool-calling loop sama sekali** — hemat biaya LLM buat pertanyaan yang jelas-jelas tidak nyambung.

### 2.5 Tool-calling loop

`ai-services/agent.py`, fungsi `run()`. Ini bagian intinya.

**Langkah 0 — suntik `search_module` (bukan nunggu model manggil)**

Hasil retrieval yang sudah dipakai buat scope gate (2.3/2.4) **langsung dimasukkan** ke riwayat percakapan seolah-olah model sudah memanggilnya:

```python
messages.append({"role": "assistant", "tool_calls": [{"function": {"name": "search_module", ...}}]})
messages.append({"role": "tool", "content": json.dumps(top_chunks)})
```

Kenapa begini (bukan cuma instruksi "panggil search_module duluan" di prompt): LLM terbukti kadang skip tool call sama sekali di giliran pertama (soal kepatuhan model, bukan bug). Dengan disuntik, model tidak pernah punya kesempatan untuk "lupa".

**Langkah 1..N — loop cari sampai cukup**

```
selama belum compose_answer dan belum MAX_TOOL_ITERATIONS (default 10):
    kirim messages + skema 5 tool ke LLM (llm_ext.chat_with_tools, tool_choice="auto")
    model pilih: panggil tool lain (search_oer/wolfram/web), ATAU compose_answer, ATAU diam
```

Urutan prioritas tool (diinstruksikan di system prompt, [detail lengkap di bawah](#tool-eksternal)):
`search_module` (sudah) → `search_oer` → `query_wolfram_alpha` → `search_academic_web` (last resort).

**Langkah penutup — paksa kalau model ngambang**

Kalau model berhenti (diam tanpa tool call, atau iterasi habis) **padahal sudah ada hasil pencarian valid** (`tool_outputs` terisi), kita tidak buang begitu saja — paksa satu panggilan terakhir dengan `tool_choice` dikunci ke `compose_answer`:

```python
forced_choice = {"type": "function", "function": {"name": "compose_answer"}}
message = llm_ext.chat_with_tools(messages, tools.TOOLS_SCHEMA, tool_choice=forced_choice)
```

Ini nyelamatin kasus model "muter-muter nyari berkali-kali lalu nyerah" — informasi yang sudah ketemu tetap dipakai, bukan hangus jadi "tidak ditemukan" padahal sebenarnya ada.

### 2.6 Grounding — verifikasi sebelum jawaban keluar

`ai-services/citations.py`, dipanggil begitu `compose_answer` terpanggil:

```python
sources = verify_citations(args["sources"], tool_outputs)
verified = [s for s in sources if s["verified"]]
if not verified:
    return NO_SOURCE_FALLBACK   # jawaban model DIBUANG, bukan diteruskan
```

Tiap `evidence` yang diklaim model di-**fuzzy-match** (threshold 85% similarity teks, `difflib.SequenceMatcher`) balik ke `tool_outputs[reference]` — konten mentah yang **benar-benar** dikembalikan tool tadi. Kalau tidak match sama sekali (model mengarang/parafrase dari pengetahuan sendiri), `verified=False`. Kalau **semua** source `verified=False`, seluruh jawaban diganti pesan jujur "tidak ditemukan" — enforcement di kode, bukan instruksi prompt yang bisa dilanggar.

`trust_tier` (untuk source tipe `web`/`oer`) **dihitung ulang di sini** dari `reference` (URL), bukan dipercaya dari isian model — lihat `trusted_domains.py`.

### 2.7 Simpan hasil

Balik ke `backend/services.py`:

```python
await self.repo.add_message(session_id, "user", question)
await self.repo.add_message(session_id, "assistant", result["message"],
    tool_calls=result["tool_calls"],   # JEJAK PROSES -- audit, tool apa dipanggil, hasil mentahnya
    citations=result["sources"],       # HASIL AKHIR -- yang ditampilkan ke siswa
    scope_klass=result["scope"]["klass"])
await self._push_history(session_id, question, result["message"])   # Redis, TTL 30 menit
```

`tool_calls` dan `citations` sengaja dipisah kolom — `tool_calls` buat debug/audit ("beneran manggil Tavily atau tidak?"), `citations` buat ditampilkan ke siswa (yang sudah lolos verifikasi).

---

## Tool Eksternal

| # | Tool | File | Kapan |
|---|---|---|---|
| 1 | `search_module` | `sync_search.py` (backend) | Selalu — sumber utama, modul divalidasi guru |
| 2 | `search_oer` | `external_tools.py` | Modul belum cukup — katalog OER kurasi manual (OpenStax, Khan Academy, dll), dibatasi ketat via parameter `include_domains` ke Tavily |
| 3 | `query_wolfram_alpha` | `external_tools.py` | HANYA cross-check numerik, bukan penjelasan konsep — Wolfram Full Results API, tier gratis 2000 call/bulan **non-komersial** |
| 4 | `search_academic_web` | `external_tools.py` | Last resort — Tavily web search umum, autentikasi header `Authorization: Bearer` (bukan `api_key` di body) |
| — | `compose_answer` | `tools.py` (skema) | Wajib dipanggil terakhir |

**Ranking domain** (`trusted_domains.py`) untuk hasil `search_academic_web` — **tidak ada yang dibuang**, semua tetap tampil tapi diberi label:

```
Tier 1: .edu / .gov / .ac.id / .go.id / arxiv.org        (regex pattern)
Tier 2: openstax.org, khanacademy.org, dll                (whitelist eksplisit)
Tier 3: SEMUA domain lain -- Wikipedia, blog, situs umum  (catch-all, label kredibilitas rendah)
```

Diurutkan tier 1 dulu; model diinstruksikan wajib kasih disclaimer eksplisit kalau cuma dapat tier 3.

---

## Referensi cepat

### File `ai-services/chatbot/` (murni komputasi, TANPA DB)

| File | Isi |
|---|---|
| `chunk.py` | Block DB → Chunk (1:1, dengan konteks heading) |
| `llm_ext.py` | Client embedding + `chat_with_tools` (OpenRouter, dukung `tool_choice` dipaksa) |
| `tools.py` | Skema 5 tool (format OpenAI function calling) |
| `external_tools.py` | Implementasi HTTP Wolfram/OER/web search |
| `trusted_domains.py` | Ranking domain (tier 1/2/3) |
| `scope_gate.py` | Keputusan inti/perluasan/di_luar_topik dari skor similarity |
| `citations.py` | Grounding check (fuzzy match) + hitung ulang trust_tier |
| `agent.py` | Orkestrator: seed search_module → tool loop → force compose → verifikasi |

### File `backend/app/domains/chatbot/` (DB + orkestrasi)

| File | Isi |
|---|---|
| `models/` | `ChapterKb` (kb_version), `BlockEmbedding` (pgvector), `ChatSession` (classroom-scoped), `ChatMessage` (tool_calls + citations terpisah) |
| `repositories/repository.py` | Query async (SQLAlchemy) — CRUD sesi/pesan, ambil block, tulis embedding |
| `sync_search.py` | Query sync (psycopg) khusus retrieval — dipanggil dari thread terpisah |
| `services.py` | Orkestrasi: reindex, mulai sesi, tanya-jawab, histori Redis |
| `router.py` | 5 endpoint HTTP (lihat di bawah) |

### Endpoint HTTP

| Method | Path | Role | Fungsi |
|---|---|---|---|
| POST | `/chatbot/chapters/{id}/reindex` | Teacher | Reindex satu bab manual |
| POST | `/chatbot/classrooms/{id}/reindex` | Teacher | Reindex semua bab published di satu kelas |
| POST | `/chatbot/sessions` | Student | Mulai sesi (body: `classroom_id`) |
| POST | `/chatbot/sessions/{id}/messages` | Student | Tanya |
| GET | `/chatbot/sessions/{id}/messages` | Student | Riwayat pesan |

### Config penting (`ai-services/.env`)

| Var | Fungsi | Efek kalau diubah |
|---|---|---|
| `CHAT_MODEL` | Model tool-calling loop | Harus dukung `tool_choice` dipaksa (function calling reliable) |
| `EMBEDDING_MODEL` / `EMBEDDING_DIM` | Model + dimensi embedding | **Wajib reindex ulang SEMUA bab** kalau ganti |
| `MAX_TOOL_ITERATIONS` | Batas giliran sebelum force-compose | Naikkan kalau sering kena "butuh waktu lebih lama" |
| `TOP_K_CHUNKS` | Jumlah chunk per `search_module` | Lebih besar = lebih lengkap tapi lebih mahal token |
| `SCOPE_SIM_HIGH` / `SCOPE_SIM_LOW` | Threshold scope gate | Perlu dikalibrasi dari data similarity nyata |
| `WOLFRAM_APP_ID` | Wolfram Alpha Full Results API | Kosong = tool ini `available: false`, tidak crash |
| `SEARCH_API_KEY` / `SEARCH_API_URL` | Tavily | Kosong = `search_oer`/`search_academic_web` `available: false` |

### Config penting (`backend/.env`)

| Var | Fungsi |
|---|---|
| `EMBEDDING_DIM` | Harus SAMA dengan `ai-services/.env` — dipakai migration bikin kolom `vector(N)` |
| `CHAT_HISTORY_TURNS` / `CHAT_HISTORY_TTL_SECONDS` | Ukuran + TTL histori percakapan di Redis |
| `QUERY_EMBEDDING_CACHE_TTL_SECONDS` / `RETRIEVAL_CACHE_TTL_SECONDS` | TTL 2 lapis cache di `sync_search.py` |
