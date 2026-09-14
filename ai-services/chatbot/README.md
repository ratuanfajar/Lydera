# Chatbot (RAG)

Chatbot tanya-jawab materi untuk siswa, berbasis RAG (Retrieval-Augmented Generation) + tool calling ke sumber eksternal. Modul ini (`ai-services/chatbot/`) murni komputasi + panggilan HTTP eksternal — **tidak menyentuh PostgreSQL/Redis**, itu tanggung jawab `backend/app/domains/chatbot/`.

## Alur singkat

```
Guru upload PDF bab -> MinerU + anotasi selesai -> blocks tersimpan
  -> reindex OTOMATIS ter-trigger (backend/app/tasks/mineru_tasks.py, langsung setelah ingest)
     (bisa juga manual: POST /chatbot/chapters/{id}/reindex atau
      POST /chatbot/classrooms/{id}/reindex untuk reindex ulang semua chapter sekaligus)
  blocks (DB) -> 1 block = 1 vector -> pgvector (block_embeddings)

Siswa tanya (sesi = 1 classroom, lintas semua bab published di situ)
  1. search_module (pgvector) -> similarity top-1 = scope gate
       rendah  -> tolak halus, stop
       tinggi  -> lanjut
       abu-abu -> LLM classifier pakai chunk paling mirip
  2. tool-calling loop: search_module -> search_oer -> query_wolfram_alpha -> search_academic_web
  3. compose_answer -> verifikasi tiap kutipan balik ke isi tool asli -> kalau nol yang valid, tolak
  4. simpan ke DB + histori hot di Redis
```

## 1. Vector DB — pgvector

- Tabel `block_embeddings`: satu baris = satu block, kolom `embedding vector(EMBEDDING_DIM)`.
- **Tidak pakai index ANN (HNSW/IVFFlat)** — model embedding default (`text-embedding-3-large`, 3072 dim) melebihi batas 2000 dim yang didukung pgvector untuk index itu. Solusinya bukan workaround, tapi memang tidak perlu: pencarian selalu di-scope ke satu `classroom_id` dulu (join `block_embeddings → chapters → modules WHERE classroom_id = ...`), jadi corpus per query cuma puluhan-ratusan baris — brute-force exact scan sudah cukup cepat.
- Query pakai operator `<=>` (cosine distance); `similarity = 1 - distance`.
- Retrieval lewat `psycopg` sync (bukan SQLAlchemy async) — lihat `backend/app/domains/chatbot/sync_search.py`. Alasannya: tool-calling loop jalan di thread terpisah (`asyncio.to_thread`), jadi tidak bisa pinjam `AsyncSession` yang terikat event loop pemanggil.

## 2. Chunking — 1 block = 1 vector, TIDAK digabung

Beda dari pendekatan RAG umum yang menggabung beberapa paragraf jadi satu chunk besar:

- Block dari `blocks` (hasil annotation: heading/text/formula/table/image, sudah tersegmentasi rapi) **langsung** jadi satu vector, apa adanya.
- **Tidak ada percabangan logika per `block_type`** — formula/table/image sudah diverbalisasi jadi teks biasa di tahap annotation (`formula.py`/`table.py`/`image.py`), chatbot tinggal embed teksnya, tidak perlu proses ulang per tipe.
- Satu-satunya "olahan": block non-heading diberi prefix heading terdekat sebagai konteks (`"A. Pengertian Turunan: Turunan pertama menyatakan..."`), supaya block pendek/berdiri sendiri tetap punya makna kontekstual.
- File: `chunk.py`, fungsi `build_chunks(chapter_id, blocks) -> list[Chunk]`.

## 3. Redis — 2 lapis cache + histori percakapan

| Apa | Key | TTL | Kenapa |
|---|---|---|---|
| Query embedding | `chatbot:emb:{hash(text+model)}` | 7 hari | Pertanyaan sama = vector sama, tidak pernah stale kecuali ganti model |
| Hasil retrieval | `chatbot:retr:{classroom_id}:{hash(query)}` | 1 jam | Skip query pgvector kalau pertanyaan sama diulang |
| Histori percakapan | `chatbot:history:{session_id}` (Redis list) | 30 menit, refresh tiap turn | Hot cache — hindari round-trip Postgres tiap giliran chat; fallback baca `chat_messages` kalau kosong |

Semua di `backend/app/domains/chatbot/sync_search.py` (embedding + retrieval cache) dan `services.py` (histori).

## 4. Scope gate — cegah pertanyaan di luar materi

Bukan cuma instruksi prompt (gampang dilanggar model) — ditegakkan di kode, `scope_gate.py`:

1. **Similarity threshold** (murah): skor top-1 hasil `search_module` ≥ `SCOPE_SIM_HIGH` → lolos langsung. ≤ `SCOPE_SIM_LOW` → tolak langsung, tanpa panggil LLM sama sekali.
2. **LLM classifier** (zona abu-abu saja): dikasih konteks chunk paling mirip yang beneran ketemu (bukan deskripsi statis), keluarkan `inti` / `perluasan` / `di_luar_topik`.
3. Aturan khusus: pertanyaan asal-usul konsep matematika (`"siapa penemu kalkulus"`) = `perluasan` (boleh), tapi kalau melebar ke biografi pribadi tokohnya = `di_luar_topik` (tolak) — dicek juga di system prompt `agent.py` supaya jawabannya sendiri tidak melebar ke situ.

## 5. Tool calling — urutan wajib

| # | Tool | Kapan |
|---|---|---|
| 1 | `search_module` | Selalu duluan — sumber utama, modul yang sudah divalidasi guru |
| 2 | `search_oer` | Modul belum cukup — katalog OER kurasi (OpenStax, Khan Academy, dll), dibatasi ketat via `include_domains` |
| 3 | `query_wolfram_alpha` | HANYA cross-check numerik, bukan penjelasan konsep — Wolfram Full Results API, tier gratis 2000 call/bulan non-komersial |
| 4 | `search_academic_web` | Last resort — web search umum (Tavily), hasil diberi `trust_tier` (1 = `.edu`/`.gov`/arxiv, 2 = OER, 3 = Wikipedia/blog/umum) dan **tetap ditampilkan semua**, tidak dibuang, cuma diurutkan tier 1 dulu |
| — | `compose_answer` | Wajib dipanggil terakhir — rincian sumber (evidence + justifikasi) + ringkasan singkat |

File: `tools.py` (skema), `external_tools.py` (implementasi HTTP), `trusted_domains.py` (ranking domain).

## 6. Grounding — jawaban wajib berdasar sumber nyata

`citations.py`:

- Tiap `evidence` yang diklaim model di-**fuzzy-match** balik ke konten mentah yang benar-benar dikembalikan tool (`verify_citations`) — bukan dipercaya mentah-mentah.
- `trust_tier` **dihitung ulang server-side** dari `reference` (URL), tidak dipercaya dari isian model (model sering salah/lupa nyalin).
- Kalau nol source yang lolos verifikasi → jawaban model **dibuang**, diganti pesan jujur "tidak ditemukan". Ini enforcement di kode (`agent.py` `_finalize`), bukan cuma prompt — supaya chatbot tidak pernah menjawab dari pengetahuan umum LLM sendiri berkedok sumber palsu.
- Jejak lengkap tiap tool call (nama, argumen, hasil mentah) ikut tersimpan ke `chat_messages.tool_calls` di DB untuk audit — terpisah dari `citations` (hasil akhir yang ditampilkan).

## Referensi file

| File | Isi |
|---|---|
| `chunk.py` | Block DB → Chunk (1:1, dengan konteks heading) |
| `llm_ext.py` | Embedding client + `chat_with_tools` (OpenRouter) |
| `tools.py` | Skema 5 tool (format OpenAI function calling) |
| `external_tools.py` | Implementasi Wolfram/OER/web search |
| `trusted_domains.py` | Ranking domain (tier 1/2/3) |
| `scope_gate.py` | Keputusan inti/perluasan/di_luar_topik |
| `citations.py` | Grounding check + hitung ulang trust_tier |
| `agent.py` | Orkestrator: scope gate → tool loop → compose_answer |

## Config penting (`ai-services/.env`, dibaca lewat `annotation/config.py`)

| Var | Fungsi |
|---|---|
| `CHAT_MODEL` | Model buat tool-calling loop (butuh reliable function calling) |
| `EMBEDDING_MODEL` / `EMBEDDING_DIM` | Model + dimensi embedding — ganti salah satu WAJIB reindex ulang semua bab |
| `MAX_TOOL_ITERATIONS` | Batas giliran tool call sebelum dipaksa jawab seadanya |
| `TOP_K_CHUNKS` | Jumlah chunk yang diambil tiap `search_module` |
| `SCOPE_SIM_HIGH` / `SCOPE_SIM_LOW` | Threshold similarity buat scope gate |
| `WOLFRAM_APP_ID` | Wolfram Alpha Full Results API |
| `SEARCH_API_KEY` / `SEARCH_API_URL` | Tavily (butuh header `Authorization: Bearer`, bukan `api_key` di body) |
