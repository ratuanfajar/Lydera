"""Skema tool (format OpenAI function calling, didukung OpenRouter) untuk agent chatbot.

`search_module` TIDAK diimplementasikan di sini -- itu butuh akses ke pgvector di PostgreSQL,
yang jadi tanggung jawab backend (lihat CONTRACT.md: ai-services tidak menyentuh DB). Backend
menyuntikkan hasil pencarian modul lewat callable `search_module_executor` ke `agent.run()`.
Tool eksternal (Wolfram/OER/web) murni HTTP, jadi diimplementasikan langsung di `external_tools.py`.
"""

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_module",
            "description": (
                "Cari di modul yang sudah dianotasi guru untuk bab yang sedang dipelajari siswa. "
                "SELALU panggil ini duluan sebelum tool lain -- modul adalah sumber utama."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_oer",
            "description": (
                "Cari materi tambahan di katalog Open Educational Resources yang sudah divetting "
                "(OpenStax, Khan Academy, Rumah Belajar Kemdikbud, MIT OCW). Panggil kalau modul "
                "tidak cukup menjawab, sebelum web search umum."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "subject": {"type": "string", "description": "topik/domain, mis. 'kalkulus'"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_wolfram_alpha",
            "description": (
                "Verifikasi HANYA jawaban numerik/komputasi matematika (hasil hitung, nilai limit, "
                "hasil integral, dsb). Mengembalikan satu baris jawaban singkat, BUKAN langkah "
                "penyelesaian -- dipakai untuk cross-check, bukan sumber penjelasan konsep."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_academic_web",
            "description": (
                "Cari di web SAAT informasi tidak ada di modul maupun OER. Hasil sudah difilter ke "
                "sumber akademik/pemerintah terpercaya saja (.edu/.gov/arxiv/dsb). LAST RESORT -- "
                "panggil paling akhir."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compose_answer",
            "description": (
                "WAJIB dipanggil untuk menutup jawaban, setelah tool pencarian yang relevan sudah "
                "dipanggil. Rincikan tiap sumber yang BENAR-BENAR dipakai dari hasil tool "
                "sebelumnya (jangan mengarang sumber baru), lalu tutup dengan ringkasan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sources": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "source_type": {
                                    "type": "string",
                                    "enum": ["modul", "oer", "wolfram_alpha", "web"],
                                },
                                "label": {"type": "string"},
                                "reference": {
                                    "type": "string",
                                    "description": (
                                        "HARUS persis disalin dari field \"reference\" di hasil tool "
                                        "search_module/search_oer/search_academic_web -- untuk modul "
                                        "cuma ANGKA polos (contoh: \"85\", BUKAN \"block_id 85\" atau "
                                        "teks lain), untuk oer/web URL utuh, untuk wolfram query yang dikirim."
                                    ),
                                },
                                "evidence": {"type": "string", "description": "kutipan LANGSUNG dari isi sumber"},
                                "justification": {"type": "string"},
                            },
                            "required": ["source_type", "label", "reference", "evidence", "justification"],
                        },
                    },
                    "summary": {
                        "type": "string",
                        "description": (
                            "Ringkasan jawaban, MAKSIMAL 2-3 kalimat, langsung ke inti, kalimat "
                            "mengalir biasa (tanpa bullet/markdown) -- dibacakan pembaca layar."
                        ),
                    },
                    "suggested_questions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "OPSIONAL, isi 1-2 pertanyaan rujukan seputar materi yang benar-benar "
                            "tersedia (dari hasil search_module) -- WAJIB diisi kalau pertanyaan "
                            "siswa majemuk dan sebagian di luar cakupan, supaya siswa tahu apa yang "
                            "masih bisa ditanyakan. Kosongkan kalau tidak perlu."
                        ),
                    },
                },
                "required": ["sources", "summary"],
            },
        },
    },
]

# Tool yang boleh dipanggil LLM murni lewat HTTP, tanpa DB (search_module dikecualikan --
# dipasok lewat search_module_executor yang diinjeksi backend).
EXTERNAL_TOOL_NAMES = {"query_wolfram_alpha", "search_oer", "search_academic_web"}
