from __future__ import annotations

import json
from typing import Callable

from annotation import config
from chatbot import retrieval_grader
from chatbot import external_tools
from quiz import jsonutil
from chatbot import llm_ext
from chatbot import scope_gate
from chatbot import tools
from chatbot.citations import verify_citations

SYSTEM_PROMPT = """# Peran
Anda asisten belajar matematika untuk siswa tunanetra -- jawaban Anda dibacakan pembaca layar.

# Aturan Grounding
- Jawab HANYA berdasarkan hasil tool yang Anda panggil. DILARANG menjawab dari pengetahuan umum
  yang tidak berdasar pada hasil tool, meskipun Anda tahu jawabannya.
- JANGAN gunakan angka/fakta dari hasil tool yang TOPIK/KONSEPNYA berbeda dari yang ditanya,
  meskipun angkanya kebetulan cocok (mis. soal grafik relasi lain yang titik puncaknya kebetulan
  sama dengan jawaban soal turunan) -- kecocokan angka bukan berarti sumbernya relevan.
- Kalau tidak ada satupun tool yang mengembalikan informasi relevan, WAJIB akui tidak menemukan
  jawabannya.

## Pengecualian: Menerapkan Metode Umum
Kalau hasil tool memuat METODE/RUMUS UMUM yang relevan (mis. "cara mencari fungsi invers adalah
menukar x dan y lalu menyelesaikan untuk x"), Anda BOLEH menerapkan metode itu ke angka spesifik
di pertanyaan siswa walau contoh angkanya tidak tertulis di sumber -- ini komputasi, bukan
mengarang, karena metodenya sendiri berasal dari sumber.
- Kutip metode/rumus itu sebagai evidence di compose_answer.
- Kalau metodenya sendiri TIDAK ADA di hasil tool manapun, tetap WAJIB mengaku tidak tahu --
  jangan mengarang metodenya juga.

# Pertanyaan Majemuk
Kalau pertanyaan siswa MAJEMUK (beberapa sub-pertanyaan digabung) dan SEBAGIAN bukan matematika
(mis. pemrograman/coding, mata pelajaran lain):
- JAWAB PENUH bagian matematikanya (pakai tool seperti biasa).
- Satu kalimat singkat menyatakan bagian lain di luar cakupan chatbot ini.
- JANGAN panggil tool apapun untuk bagian non-matematika itu, walau Anda tahu jawabannya.
- Tutup dengan 1-2 pertanyaan rujukan (`suggested_questions` di compose_answer).

# Tool
`search_module` SUDAH otomatis dipanggilkan sistem untuk pertanyaan ini -- cek hasilnya di riwayat
percakapan dulu sebelum manggil tool lain. Kalau sudah cukup, LANGSUNG `compose_answer`.

## Urutan Eskalasi (kalau search_module belum cukup)
1. `search_oer` -- cari materi tambahan terstruktur
2. `query_wolfram_alpha` -- HANYA cross-check hasil numerik/komputasi, bukan penjelasan konsep
3. `search_academic_web` -- LAST RESORT, kalau modul dan OER berdua tidak menjawab

## Batasan
Jatah panggilan tool TERBATAS -- jangan ulangi tool yang sama dengan query mirip. Untuk pertanyaan
overview (mis. "bab ini bahas apa"), JANGAN cari satu chunk berisi daftar lengkap topik -- itu
biasanya tidak ada. Simpulkan dari HEADING-heading yang sudah muncul di hasil `search_module`.

Setelah informasi cukup untuk menjawab (tidak harus sempurna), LANGSUNG panggil `compose_answer`.

# Kepercayaan Sumber
Hasil `search_academic_web` punya `trust_tier`: 1 (.edu/.gov/arxiv), 2 (OER kurasi), 3
(Wikipedia/blog/situs umum). SELALU utamakan tier 1/2. Kalau cuma dapat tier 3, tetap boleh
dipakai TAPI wajib sebutkan eksplisit di summary bahwa sumbernya belum sepenuhnya terverifikasi.

# Cakupan: Sejarah/Asal-usul Konsep
Kalau pertanyaan menyinggung asal-usul suatu konsep matematika (mis. "siapa yang menemukan konsep
ini"), jawab SEBATAS konteks historis singkat (siapa, kira-kira kapan/di peradaban mana) -- JANGAN
masuk ke biografi pribadi tokohnya (riwayat hidup, karier, kehidupan pribadi).

# Gaya Jawaban ke Siswa
SINGKAT dan LANGSUNG KE INTI (maksimal 2-3 kalimat untuk summary) -- siswa mendengarkan lewat
pembaca layar. JANGAN pakai bullet/heading markdown di jawaban (tidak enak dibacakan) -- tulis
sebagai kalimat mengalir biasa.

# Menutup Jawaban
WAJIB tutup dengan memanggil `compose_answer`: rincikan tiap sumber yang benar-benar dipakai
(kutipan langsung dari isi tool result sebagai evidence, dan justifikasi kenapa relevan), lalu
satu ringkasan singkat di akhir."""

NO_SOURCE_FALLBACK = (
    "Maaf, informasi ini tidak ditemukan di modul, materi tambahan, maupun sumber akademik yang "
    "tersedia. Coba tanyakan dengan kata lain, atau tanyakan ke gurumu langsung."
)

OUT_OF_SCOPE_MESSAGE = (
    "Pertanyaan itu di luar materi yang tersedia di kelasmu. Coba tanya soal konsep, cara hitung, "
    "atau penerapan dari bab-bab yang sudah dipelajari ya."
)


def run(
    question: str,
    history: list[dict],
    search_module_executor: Callable[[str], list[dict]],
) -> dict:
    """`history`: list turn sebelumnya [{"role": "user"|"assistant", "content": str}, ...].
    `search_module_executor(query) -> list[dict]` dengan tiap dict {reference, text, similarity,
    heading, ...}, dipasok backend (query pgvector lintas semua chapter published di classroom
    siswa, lihat `sync_search.py`).

    Balikkan {"status": "out_of_scope"|"answered", "message": str, "sources": list[dict] | None,
    "scope": dict}.
    """
    top_chunks = search_module_executor(question)
    scope = scope_gate.check_scope(question, top_chunks)

    if scope["klass"] == "di_luar_topik":
        return {
            "status": "out_of_scope",
            "message": OUT_OF_SCOPE_MESSAGE,
            "sources": None,
            "suggested_questions": None,
            "tool_calls": [],
            "scope": scope,
        }

    relevant_chunks, seed_result_text = retrieval_grader.evaluate(question, top_chunks)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history, {"role": "user", "content": question}]
    tool_outputs: dict[str, str] = {}
    tool_call_log: list[dict] = [] 

    seed_args = {"query": question}
    for chunk in relevant_chunks:
        tool_outputs[str(chunk["reference"])] = chunk["text"]
    messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "seed_search_module",
            "type": "function",
            "function": {"name": "search_module", "arguments": json.dumps(seed_args, ensure_ascii=False)},
        }],
    })
    messages.append({"role": "tool", "tool_call_id": "seed_search_module", "content": seed_result_text})
    tool_call_log.append({"name": "search_module", "arguments": json.dumps(seed_args, ensure_ascii=False), "result": seed_result_text})

    for _ in range(config.MAX_TOOL_ITERATIONS):
        message = llm_ext.chat_with_tools(messages, tools.TOOLS_SCHEMA)
        messages.append(_assistant_message_dict(message))

        if not message.tool_calls:
            if tool_outputs:
                return _force_compose(messages, tool_outputs, tool_call_log, scope)
            return {
                "status": "answered",
                "message": NO_SOURCE_FALLBACK,
                "sources": [],
                "suggested_questions": None,
                "tool_calls": tool_call_log,
                "scope": scope,
            }

        compose_call = next((tc for tc in message.tool_calls if tc.function.name == "compose_answer"), None)
        if compose_call is not None:
            return _finalize(compose_call, tool_outputs, tool_call_log, scope)

        for call in message.tool_calls:
            result_text = _dispatch(call, search_module_executor, tool_outputs)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result_text})
            tool_call_log.append({"name": call.function.name, "arguments": call.function.arguments, "result": result_text})

    if tool_outputs:
        return _force_compose(messages, tool_outputs, tool_call_log, scope)
    return {
        "status": "answered",
        "message": "Maaf, butuh waktu lebih lama untuk merangkai jawaban ini. Coba tanyakan lebih spesifik ya.",
        "sources": [],
        "suggested_questions": None,
        "tool_calls": tool_call_log,
        "scope": scope,
    }


def _force_compose(messages: list[dict], tool_outputs: dict[str, str], tool_call_log: list[dict], scope: dict) -> dict:
    """Paksa satu panggilan terakhir dengan `tool_choice` dikunci ke compose_answer, supaya hasil
    pencarian yang sudah valid tidak terbuang gara-gara model tidak menutup sendiri dengan rapi."""
    forced_choice = {"type": "function", "function": {"name": "compose_answer"}}
    message = llm_ext.chat_with_tools(messages, tools.TOOLS_SCHEMA, tool_choice=forced_choice)
    compose_call = next((tc for tc in (message.tool_calls or []) if tc.function.name == "compose_answer"), None)
    if compose_call is None:
        return {
            "status": "answered",
            "message": NO_SOURCE_FALLBACK,
            "sources": [],
            "suggested_questions": None,
            "tool_calls": tool_call_log,
            "scope": scope,
        }
    return _finalize(compose_call, tool_outputs, tool_call_log, scope)


def _assistant_message_dict(message) -> dict:
    msg = {"role": "assistant", "content": message.content}
    if message.tool_calls:
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in message.tool_calls
        ]
    return msg


def _dispatch(call, search_module_executor: Callable[[str], list[dict]], tool_outputs: dict[str, str]) -> str:
    try:
        args = json.loads(call.function.arguments or "{}")
    except json.JSONDecodeError:
        args = {}

    name = call.function.name
    if name == "search_module":
        query = args.get("query", "")
        chunks = search_module_executor(query)
        relevant, result_text = retrieval_grader.evaluate(query, chunks)
        for chunk in relevant:
            tool_outputs[str(chunk["reference"])] = chunk["text"]
        return result_text

    if name == "query_wolfram_alpha":
        result = external_tools.query_wolfram_alpha(args.get("query", ""))
        if result.get("answer"):
            tool_outputs[args.get("query", "")] = result["answer"]
        return json.dumps(result, ensure_ascii=False)

    if name == "search_oer":
        result = external_tools.search_oer(args.get("query", ""), args.get("subject", ""))
        for item in result.get("results", []):
            tool_outputs[item["url"]] = f"{item['title']} {item['snippet']}"
        return json.dumps(result, ensure_ascii=False)

    if name == "search_academic_web":
        result = external_tools.search_academic_web(args.get("query", ""))
        for item in result.get("results", []):
            tool_outputs[item["url"]] = f"{item['title']} {item['snippet']}"
        return json.dumps(result, ensure_ascii=False)

    return json.dumps({"error": f"tool tidak dikenal: {name}"})


def _finalize(compose_call, tool_outputs: dict[str, str], tool_call_log: list[dict], scope: dict) -> dict:
    try:
        args = jsonutil.parse_json(compose_call.function.arguments)
    except Exception:
        args = {"sources": [], "summary": compose_call.function.arguments}

    sources = verify_citations(args.get("sources", []), tool_outputs)
    verified = [s for s in sources if s.get("verified")]
    suggested_questions = args.get("suggested_questions") or None

    if not verified:
        return {
            "status": "answered",
            "message": NO_SOURCE_FALLBACK,
            "sources": sources,
            "suggested_questions": None,
            "tool_calls": tool_call_log,
            "scope": scope,
        }

    return {
        "status": "answered",
        "message": args.get("summary", ""),
        "sources": sources,
        "suggested_questions": suggested_questions,
        "tool_calls": tool_call_log,
        "scope": scope,
    }
