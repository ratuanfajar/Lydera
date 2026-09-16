"""Orkestrator chatbot: scope gate -> tool-calling loop -> verifikasi kutipan -> jawaban akhir.

Murni komputasi + panggilan HTTP eksternal (OpenRouter, embedding provider, Wolfram, search API) --
TIDAK menyentuh PostgreSQL. Pencarian modul (`search_module`) butuh pgvector di DB, jadi backend
yang menyediakan hasilnya lewat `search_module_executor` (callable), sama semangatnya dengan
`quiz_pipeline.compute_for_chapter` menerima `blocks` yang sudah dibaca backend dari DB -- di sini
bentuknya callable, bukan data statis, karena tool calling itu interaktif (LLM yang memutuskan
kapan dan berapa kali memanggil)."""

from __future__ import annotations

import json
from typing import Callable

import config
import external_tools
import jsonutil
import llm_ext
import scope_gate
import tools
from citations import verify_citations

SYSTEM_PROMPT = (
    "Anda adalah asisten belajar matematika untuk siswa tunanetra (jawaban dibacakan pembaca "
    "layar). Jawab HANYA berdasarkan hasil tool yang Anda panggil -- DILARANG menjawab dari "
    "pengetahuan umum Anda sendiri, meskipun Anda tahu jawabannya. Kalau tidak ada satupun tool "
    "yang mengembalikan informasi relevan, WAJIB akui tidak menemukan jawabannya -- jangan "
    "menutupi itu dengan pengetahuan umum.\n\n"
    "Kalau pertanyaan siswa MAJEMUK (beberapa sub-pertanyaan digabung) dan SEBAGIAN bukan "
    "matematika (mis. pemrograman/coding, mata pelajaran lain): JAWAB PENUH bagian matematikanya "
    "(pakai tool seperti biasa), lalu satu kalimat singkat menyatakan bagian lain di luar cakupan "
    "chatbot ini. JANGAN panggil tool apapun untuk bagian non-matematika itu, walau Anda tahu "
    "jawabannya. Tutup dengan 1-2 pertanyaan rujukan (suggested_questions di compose_answer) "
    "seputar materi yang tersedia, supaya siswa tahu apa yang masih bisa ditanyakan.\n\n"
    "search_module untuk pertanyaan ini SUDAH otomatis dipanggilkan sistem -- cek dulu hasilnya di "
    "riwayat percakapan sebelum manggil tool lain. Kalau hasilnya sudah cukup, LANGSUNG compose_answer, "
    "tidak perlu manggil search_module lagi. Kalau belum cukup, urutan tool berikutnya WAJIB diikuti:\n"
    "1. search_oer -- kalau modul belum cukup, cari materi tambahan terstruktur\n"
    "2. query_wolfram_alpha -- HANYA untuk cross-check hasil numerik/komputasi, bukan penjelasan konsep\n"
    "3. search_academic_web -- LAST RESORT, kalau modul dan OER berdua tidak menjawab\n\n"
    "Jatah panggilan tool TERBATAS -- jangan ulangi tool yang sama dengan query yang mirip-mirip. "
    "Untuk pertanyaan overview (mis. \"materinya apa aja\", \"bab ini bahas apa\"), JANGAN cari "
    "chunk yang berisi daftar lengkap topik -- itu biasanya tidak ada satu chunk pun yang persis "
    "begitu. Simpulkan dari HEADING-heading berbeda yang sudah muncul di hasil search_module "
    "sejauh ini, itu sudah cukup.\n\n"
    "Setelah dapat informasi yang cukup untuk menjawab (tidak harus sempurna), LANGSUNG panggil "
    "compose_answer -- jangan terus mencari sumber tambahan kalau yang sudah ada sudah cukup.\n\n"
    "Hasil search_academic_web punya trust_tier: 1 (.edu/.gov/arxiv, paling terpercaya), 2 (OER "
    "kurasi), 3 (Wikipedia/blog/situs umum, kurang terpercaya). SELALU utamakan sumber tier 1/2 "
    "kalau ada. Kalau cuma dapat tier 3, tetap boleh dipakai TAPI wajib sebutkan eksplisit di "
    "summary bahwa sumbernya belum sepenuhnya terverifikasi/akademik formal.\n\n"
    "Gaya jawaban: SINGKAT dan LANGSUNG KE INTI (maksimal 2-3 kalimat untuk summary) -- siswa "
    "mendengarkan lewat pembaca layar, bukan membaca teks panjang. Jangan pakai bullet/heading "
    "markdown (tidak enak dibacakan), tulis sebagai kalimat mengalir biasa.\n\n"
    "Kalau pertanyaan menyinggung asal-usul/sejarah suatu konsep matematika (mis. 'siapa yang "
    "menemukan konsep ini'), jawab SEBATAS konteks historis singkat konsepnya (siapa, kira-kira "
    "kapan/di peradaban mana) -- JANGAN masuk ke biografi pribadi tokohnya (riwayat hidup, "
    "karier lain, kehidupan pribadi). Itu bukan lagi materi matematika.\n\n"
    "Setelah selesai mengumpulkan informasi, WAJIB tutup dengan memanggil compose_answer: rincikan "
    "tiap sumber yang benar-benar dipakai (dengan kutipan langsung dari isi tool result sebagai "
    "evidence, dan justifikasi kenapa itu relevan), lalu satu ringkasan singkat di akhir."
)

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
    # Panggil search_module lebih dulu buat scope gate -- skor similarity top-1 nya sendiri yang
    # jadi sinyal relevansi, bukan bandingkan ke anchor topik statis. Kalau model nanti manggil
    # search_module lagi dengan query sama persis di dalam loop, kena cache Redis (sync_search.py),
    # jadi tidak ada biaya tambahan berarti.
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

    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history, {"role": "user", "content": question}]
    tool_outputs: dict[str, str] = {}
    tool_call_log: list[dict] = []  # jejak audit -- tool apa dipanggil, argumen apa, hasil mentahnya apa

    # Suntikkan hasil search_module (sudah kepanggil di atas buat scope gate) sebagai giliran tool
    # PERTAMA di riwayat -- model tidak punya kesempatan "lupa" manggil search_module duluan,
    # karena dari sudut pandang model itu sudah terjadi. Ini enforcement di kode, bukan cuma
    # instruksi prompt "selalu panggil search_module dulu" yang terbukti bisa dilanggar model.
    seed_args = {"query": question}
    seed_result_text = json.dumps(top_chunks, ensure_ascii=False)
    for chunk in top_chunks:
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
            # Model berhenti tanpa manggil tool giliran ini -- kalau sebelumnya SUDAH ada hasil
            # pencarian valid (tool_outputs terisi), jangan buang begitu saja: paksa dia nutup
            # jawaban dari apa yang sudah terkumpul (lihat _force_compose). Cuma kalau memang
            # belum ada dasar apapun yang jadi "tidak ditemukan".
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

    # Habis iterasi tanpa compose_answer -- kalau ada hasil pencarian valid, paksa nutup dari itu
    # (lihat _force_compose), jangan buang cuma karena model kebanyakan muter nyari.
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
    """Model kehabisan giliran atau berhenti begitu saja padahal sudah ada hasil pencarian valid --
    paksa satu panggilan terakhir dengan tool_choice dikunci ke compose_answer (bukan "auto"),
    supaya dia WAJIB menyimpulkan dari yang sudah terkumpul, bukan biarkan informasi valid
    terbuang gara-gara model tidak menutup sendiri dengan rapi."""
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
        chunks = search_module_executor(args.get("query", ""))
        for chunk in chunks:
            tool_outputs[str(chunk["reference"])] = chunk["text"]
        return json.dumps(chunks, ensure_ascii=False)

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

    # Enforcement di KODE, bukan cuma instruksi prompt -- tanpa source yang benar-benar
    # terverifikasi ke isi tool result, jawaban model tidak boleh diteruskan ke siswa apa adanya
    # (kemungkinan besar itu pengetahuan umum model, bukan hasil grounding).
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
