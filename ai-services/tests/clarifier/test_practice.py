import json
from types import SimpleNamespace

import pytest

from clarifier import agent, practice, retrieval_grader, scope_gate

SOAL = {
    "question_text": "Berapa keliling persegi bersisi 5?",
    "options": {"A": "20", "B": "25", "C": "10", "D": "15"},
    "correct_option": "A",
    "langkah": ["Keliling persegi empat kali sisi.", "Empat kali lima sama dengan dua puluh."],
    "kesimpulan": "Kelilingnya dua puluh.",
    "markup": None,
    "stimulus": None,
    "bloom_level": 2,
    "analisis_level": "rahasia",
}


def chunk(reference, text, heading="Keliling"):
    return {"reference": reference, "text": text, "heading": heading, "similarity": 0.8}


@pytest.fixture
def grader(monkeypatch):
    def install(references):
        monkeypatch.setattr(retrieval_grader, "grade_chunks", lambda topic, chunks: {"verdict": "correct", "relevant_references": references})

    return install


def test_sumber_hanya_dari_bagian_relevan_dengan_judul_unik(grader):
    grader(["1", "3"])
    chunks = [chunk(1, "Teks satu."), chunk(2, "Teks dua."), chunk(3, "Teks tiga.")]
    source = practice.select_source("keliling", lambda topic: chunks)
    assert source["text"] == "Teks satu.\n\nTeks tiga." and source["headings"] == ["Keliling"]


def test_tanpa_bagian_relevan_tidak_ada_sumber(grader):
    grader([])
    assert practice.select_source("keliling", lambda topic: [chunk(1, "Teks.")]) is None


def test_sumber_dipotong_ke_batas_karakter(grader, monkeypatch):
    grader(["1"])
    monkeypatch.setattr(practice.config, "PRACTICE_SOURCE_MAX_CHARS", 10)
    assert len(practice.select_source("t", lambda topic: [chunk(1, "x" * 50)])["text"]) == 10


@pytest.mark.parametrize("text,expected", [("B", "B"), ("b", "B"), (" c. ", "C"), ("jawaban D", "D"), ("Jawabanku: a", "A"), ("opsi B!", "B")])
def test_pilihan_jawaban_dikenali(text, expected):
    assert practice.parse_choice(text) == expected


@pytest.mark.parametrize("text", ["E", "AB", "apa itu lingkaran", "jawabannya B karena luas", "", "a b"])
def test_bukan_pilihan_jawaban(text):
    assert practice.parse_choice(text) is None


def test_soal_di_chat_memuat_label_pilihan_dan_petunjuk_tanpa_kunci():
    reply = practice.question_reply(practice.stored_form(SOAL, ["Keliling"]))
    message = reply["message"]
    assert message.splitlines()[0] == practice.config.PRACTICE_LABEL
    assert "Soal: Berapa keliling persegi bersisi 5?" in message and "Pilihan D: 15" in message
    assert message.endswith("Ketik huruf pilihanmu: A, B, C, atau D.")
    for secret in ("Langkah", "Kesimpulan", "Jawaban yang benar", "rahasia"):
        assert secret not in message
    assert reply["message_markup"] is None and reply["latihan"] == {"tahap": "soal", "pilihan": ["A", "B", "C", "D"]}
    assert reply["status"] == "answered" and reply["sources"] == [] and reply["scope"]["klass"] == "inti"


def test_soal_di_chat_menampilkan_markup_dan_stimulus_bila_ada():
    markup = {"question": "$x$?", "options": {"A": "$1$", "B": "$2$", "C": "$3$", "D": "$4$"}, "langkah": ["$a$"], "kesimpulan": "$b$"}
    stimulus = {"readable_text": "Teks stimulus.", "source_markup": "Teks $s$."}
    reply = practice.question_reply(practice.stored_form({**SOAL, "markup": markup, "stimulus": stimulus}, []))
    assert "Teks stimulus." in reply["message"] and "$" not in reply["message"]
    assert "Teks $s$." in reply["message_markup"] and "Soal: $x$?" in reply["message_markup"] and "Pilihan A: $1$" in reply["message_markup"]


@pytest.mark.parametrize("chosen,correct", [("A", True), ("B", False)])
def test_hasil_jawaban_membuka_kunci_langkah_dan_label(chosen, correct):
    reply = practice.answer_reply(practice.stored_form(SOAL, []), chosen)
    lines = reply["message"].splitlines()
    assert lines[0] == ("Jawabanmu benar." if correct else "Jawabanmu salah.") + " Jawaban yang benar opsi A, yaitu 20."
    assert "Langkah 2. Empat kali lima sama dengan dua puluh." in lines and "Kesimpulan: Kelilingnya dua puluh." in lines
    assert lines[-1] == practice.config.PRACTICE_LABEL
    assert reply["latihan"] == {"tahap": "hasil", "benar": correct}


def test_hasil_jawaban_tidak_menggandakan_titik_di_akhir_teks_opsi():
    soal = {**SOAL, "options": {**SOAL["options"], "A": "Garis pertama, karena menyentuh."}}
    reply = practice.answer_reply(practice.stored_form(soal, []), "A")
    assert "yaitu Garis pertama, karena menyentuh." in reply["message"] and ".." not in reply["message"]


def test_hasil_jawaban_punya_markup_bila_soal_berrumus():
    markup = {"question": "q", "options": {"A": "$20$", "B": "b", "C": "c", "D": "d"}, "langkah": ["$4 + 5$"], "kesimpulan": "$20$"}
    reply = practice.answer_reply(practice.stored_form({**SOAL, "markup": markup}, []), "A")
    assert "Langkah 1. $4 + 5$" in reply["message_markup"] and "$" not in reply["message"]


def test_bentuk_simpan_bisa_di_json_dan_kembali():
    stored = practice.stored_form(SOAL, ["Keliling"])
    assert json.loads(json.dumps(stored)) == stored


def call(name, arguments):
    return SimpleNamespace(id="c1", function=SimpleNamespace(name=name, arguments=json.dumps(arguments)))


@pytest.fixture
def agent_stub(monkeypatch):
    seen = {"calls": 0}
    monkeypatch.setattr(scope_gate, "check_scope", lambda question, chunks: {"klass": "inti", "similarity": 0.9})
    monkeypatch.setattr(retrieval_grader, "evaluate", lambda question, chunks: ([], "[]"))

    def chat(messages, schema, tool_choice=None):
        seen["calls"] += 1
        return SimpleNamespace(content=None, tool_calls=[seen["call"]])

    monkeypatch.setattr(agent.llm_ext, "chat_with_tools", chat)
    return seen


@pytest.mark.parametrize("arguments,expected", [
    ({"topic": " garis singgung "}, {"topic": "garis singgung", "level": 3}),
    ({"topic": "peluang", "level": 1}, {"topic": "peluang", "level": 1}),
    ({"topic": "peluang", "level": 9}, {"topic": "peluang", "level": 3}),
    ({"topic": "peluang", "level": "dua"}, {"topic": "peluang", "level": 3}),
])
def test_agen_meneruskan_permintaan_latihan_tanpa_menjawab(agent_stub, arguments, expected):
    agent_stub["call"] = call("request_practice", arguments)
    result = agent.run("Buatkan soal latihan", [], lambda q: [])
    assert result["status"] == "practice_requested" and result["practice"] == expected
    assert agent_stub["calls"] == 1 and result["sources"] == []
