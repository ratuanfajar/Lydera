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
                "Cari materi tambahan di sumber Open Educational Resources yang sudah dikurasi "
                "(OpenStax, Khan Academy, Ruang Murid Kemendikdasmen, dan Repositori Kemendikdasmen berupa "
                "modul PDF untuk guru). Hanya hasil berskor relevansi tinggi yang dikembalikan; bisa kosong. "
                "Panggil kalau modul tidak cukup menjawab."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "frasa topik singkat tanpa kata tanya"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_practice",
            "description": (
                "Panggil HANYA bila siswa meminta dibuatkan soal latihan. Sistem yang membuat dan memeriksa soalnya; "
                "Anda tidak boleh menulis soal sendiri. Setelah memanggil ini, jangan panggil tool lain."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "topik latihan sebagai frasa singkat tanpa kata perintah, sesuai permintaan siswa"},
                    "level": {"type": "integer", "description": "OPSIONAL, 1 sampai 3: 1 mengingat, 2 memahami, 3 menerapkan; bawaan 3"},
                },
                "required": ["topic"],
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
                                    "enum": ["modul", "oer"],
                                },
                                "label": {
                                    "type": "string",
                                    "description": (
                                        "Nama sumber singkat dalam kalimat biasa berbahasa Indonesia, tanpa URL, tanpa tanda pisah "
                                        "atau garis tegak, tanpa ekstensi berkas, garis bawah, atau kode seperti KD 3.5 dan KK B. "
                                        "Contoh: Ruang Murid, materi lingkaran dan busur lingkaran; Repositori Kemendikdasmen, "
                                        "modul matematika kelas sebelas, bab lingkaran. "
                                        "Untuk modul: judul bagian atau bab dari heading, bukan nomor."
                                    ),
                                },
                                "reference": {
                                    "type": "string",
                                    "description": (
                                        "HARUS persis disalin dari field \"reference\" di hasil tool "
                                        "search_module (cuma ANGKA polos, contoh: \"85\", BUKAN "
                                        "\"block_id 85\" atau teks lain) atau dari field \"url\" di hasil search_oer (URL utuh)."
                                    ),
                                },
                                "evidence": {"type": "string", "description": "satu atau dua kalimat utuh dari isi sumber, tanpa kalimat yang terpotong dan tanpa fragmen rumus yang berantakan; bila rumusnya berantakan, kutip kalimat narasi di sekitarnya"},
                                "justification": {
                                    "type": "string",
                                    "description": (
                                        "Satu kalimat Indonesia tentang alasan sumber relevan, tanpa simbol matematika mentah. "
                                        "Kalau evidence berbahasa Inggris, sebut intinya dalam bahasa Indonesia."
                                    ),
                                },
                            },
                            "required": ["source_type", "label", "reference", "evidence", "justification"],
                        },
                    },
                    "summary": {
                        "type": "string",
                        "description": (
                            "Ringkasan jawaban, MAKSIMAL 3 kalimat inti, langsung ke inti, kalimat mengalir biasa. "
                            "Tanpa markdown dan tanpa pembuka seperti 'Berikut' atau 'Jadi'. Rumus matematika ditulis "
                            "dalam LaTeX di antara tanda dolar, mis. $(x - h)^2 + (y - k)^2 = r^2$; sistem mengubahnya "
                            "menjadi kata untuk pembaca layar, jadi jangan menulis simbol di luar tanda dolar. "
                            "Satuan ditulis lengkap ('kilometer per jam'). "
                            "Dibacakan pembaca layar."
                        ),
                    },
                    "tabel": {
                        "type": "object",
                        "description": (
                            "OPSIONAL. Sertakan HANYA bila sumber memuat data berbentuk tabel atau jawabannya perbandingan beberapa "
                            "nilai atau sifat; selain itu kosongkan. Bentuk {\"judul\": \"...\", \"kolom\": [\"...\"], "
                            "\"baris\": [[\"...\"]]} dengan jumlah sel tiap baris sama dengan jumlah kolom. Semua sel teks biasa "
                            "tanpa markdown; rumus ditulis LaTeX di antara tanda dolar. Semua angka harus berasal dari hasil tool atau "
                            "ringkasan. Maksimal sekitar 8 baris. Summary tetap harus bisa dipahami tanpa tabel dan tidak boleh merujuk "
                            "'tabel di atas'."
                        ),
                    },
                    "suggested_questions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "OPSIONAL, isi 1-2 pertanyaan rujukan seputar materi yang benar-benar "
                            "tersedia (dari hasil search_module) -- WAJIB diisi kalau pertanyaan "
                            "siswa majemuk dan sebagian di luar cakupan, supaya siswa tahu apa yang "
                            "masih bisa ditanyakan. Kosongkan kalau tidak perlu. Tulis seperti diucapkan: "
                            "tanpa simbol matematika mentah dan tanpa markdown."
                        ),
                    },
                },
                "required": ["sources", "summary"],
            },
        },
    },
]
