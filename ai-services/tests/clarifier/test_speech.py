import json
from types import SimpleNamespace

import pytest

from clarifier import agent, speech
from common import math_text


@pytest.fixture
def verbalizer(monkeypatch):
    calls = []

    def convert(latex):
        calls.append(latex)
        return f"<{latex}>", []

    monkeypatch.setattr(math_text, "convert_checked", convert)
    return calls


def test_teks_tanpa_rumus_dikembalikan_apa_adanya(verbalizer):
    assert speech.derive_message("Fungsi memetakan setiap anggota domain.") == ("Fungsi memetakan setiap anggota domain.", None, [])
    assert verbalizer == []


def test_rumus_menjadi_bacaan_dan_markup_dipertahankan(verbalizer):
    text = "Persamaannya $x^2 = 4$ dengan pusat $P(a, b)$."
    spoken, markup, issues = speech.derive_message(text)
    assert spoken == "Persamaannya <x^2 = 4> dengan pusat <P(a, b)>."
    assert markup == text
    assert issues == []
    assert "$" not in spoken


def test_rumus_yang_sama_diverbalisasi_sekali(verbalizer):
    speech.derive_message("$x$ lalu $x$ lagi $y$")
    assert sorted(verbalizer) == ["x", "y"]


@pytest.mark.parametrize(
    "text",
    ["Rusak $x^2 belum ditutup.", "Rumus kosong $ $ di sini.", "Kurung $\\frac{1}{2$ tidak seimbang.", "Pasangan $\\left( x$ tak lengkap."],
)
def test_latex_tidak_valid_menghapus_markup_dan_tanda_dolar(verbalizer, text):
    spoken, markup, issues = speech.derive_message(text)
    assert markup is None
    assert issues
    assert "$" not in spoken
    assert verbalizer == []


def test_temuan_verbalizer_menghapus_markup_tetapi_mempertahankan_bacaan(monkeypatch):
    monkeypatch.setattr(math_text, "convert_checked", lambda latex: ("bacaan terbaik", ["angka 7 hilang"]))
    spoken, markup, issues = speech.derive_message("Nilai $x = 7$.")
    assert spoken == "Nilai bacaan terbaik."
    assert markup is None
    assert any("angka 7 hilang" in issue for issue in issues)


def compose(summary):
    arguments = json.dumps({
        "sources": [{"source_type": "modul", "label": "m", "reference": "85", "evidence": "sudut pusat dua kali sudut keliling", "justification": "j"}],
        "summary": summary,
    })
    return SimpleNamespace(function=SimpleNamespace(arguments=arguments))


def finalize(summary):
    outputs = {"85": "sudut pusat dua kali sudut keliling pada busur yang sama"}
    return agent._finalize(compose(summary), outputs, [], {"klass": "inti"})


def test_finalize_mengisi_message_dan_message_markup(verbalizer):
    result = finalize("Besar sudut pusat adalah $2\\alpha$ pada busur itu.")
    assert result["message"] == "Besar sudut pusat adalah <2\\alfa> pada busur itu."
    assert result["message_markup"] == "Besar sudut pusat adalah $2\\alpha$ pada busur itu."
    assert result["format_issues"] == []


BS = chr(92)


@pytest.mark.parametrize("slashes", [1, 2])
def test_finalize_menjaga_perintah_latex_baik_dengan_satu_maupun_dua_backslash(verbalizer, slashes):
    raw_summary = "Nilai $" + BS * slashes + "frac{1}{2}$ dan $" + BS * slashes + "times 3$ sudah benar."
    raw = '{"sources": [{"source_type": "modul", "label": "m", "reference": "85", "evidence": "sudut pusat dua kali sudut keliling", "justification": "j"}], "summary": "' + raw_summary + '"}'
    call = SimpleNamespace(function=SimpleNamespace(arguments=raw))
    result = agent._finalize(call, {"85": "sudut pusat dua kali sudut keliling"}, [], {"klass": "inti"})
    assert result["message_markup"] == "Nilai $" + BS + "frac{1}{2}$ dan $" + BS + "times 3$ sudah benar."


def test_finalize_tanpa_rumus_tidak_punya_markup(verbalizer):
    result = finalize("Sudut pusat dua kali sudut keliling.")
    assert result["message"] == "Sudut pusat dua kali sudut keliling."
    assert result["message_markup"] is None


def test_finalize_rumus_rusak_tidak_menampilkan_markup(verbalizer):
    result = finalize("Besarnya $2\\alpha belum ditutup.")
    assert result["message_markup"] is None
    assert "$" not in result["message"]
    assert result["format_issues"]


def test_finalize_tanpa_sumber_terverifikasi_memakai_pesan_cadangan(verbalizer):
    arguments = json.dumps({"sources": [{"source_type": "modul", "label": "m", "reference": "85", "evidence": "kalimat karangan sama sekali", "justification": "j"}], "summary": "Isi $x$."})
    call = SimpleNamespace(function=SimpleNamespace(arguments=arguments))
    result = agent._finalize(call, {"85": "teks sumber lain"}, [], {"klass": "inti"})
    assert result["message"] == agent.NO_SOURCE_FALLBACK
    assert result.get("message_markup") is None


def test_system_prompt_meminta_latex_di_summary_dan_kata_di_bidang_lain():
    assert "LaTeX di antara tanda dolar" in agent.SYSTEM_PROMPT
    assert "jangan memakai tanda dolar atau simbol" in agent.SYSTEM_PROMPT


def raise_error(latex):
    raise RuntimeError("verbalizer mati")


def test_verbalizer_gagal_memberi_bacaan_darurat_tanpa_markup(monkeypatch):
    monkeypatch.setattr(math_text, "convert_checked", raise_error)
    spoken, markup, issues = speech.derive_message("Nilai $x^2 = 4$ benar.")
    assert markup is None
    assert issues == ["Verbalizer rumus gagal: RuntimeError"]
    assert "$" not in spoken and "^" not in spoken and "=" not in spoken


def test_bacaan_darurat_tidak_memuat_sisa_sintaks_latex(verbalizer):
    spoken, markup, _ = speech.derive_message("Hasil $" + BS + "frac{a}{b}$ dan $x^2_1$ belum ditutup $.")
    assert markup is None
    for char in (BS, "{", "}", "^", "_", "$"):
        assert char not in spoken
    assert "a per b" in spoken


def test_dolar_ter_escape_dibaca_dolar_dan_tanpa_markup(verbalizer):
    spoken, markup, issues = speech.derive_message("Harganya \\$5 saja.")
    assert "dolar" in spoken and "$" not in spoken and BS not in spoken
    assert markup is None
    assert issues == []


@pytest.mark.parametrize("command", ["href", "url", "includegraphics", "input", "htmlClass", "def"])
def test_perintah_latex_di_luar_daftar_putih_menghapus_markup(verbalizer, command):
    spoken, markup, issues = speech.derive_message("Lihat $" + BS + command + "{http://x.test}{teks}$ ini.")
    assert markup is None
    assert any("tidak diizinkan" in issue and command in issue for issue in issues)
    assert verbalizer == []


def test_jumlah_rumus_dan_panjang_teks_dibatasi(verbalizer):
    banyak = " ".join(f"$x_{i}$" for i in range(speech.MAX_FORMULAS + 1))
    assert speech.derive_message(banyak)[1] is None
    panjang = "$x$ " + "kata " * speech.MAX_MARKUP_CHARS
    assert speech.derive_message(panjang)[1] is None


def test_simbol_di_luar_tanda_dolar_menghapus_markup_dan_diganti_kata(verbalizer):
    spoken, markup, issues = speech.derive_message("Jadi x^2 + y^2 = r^2 dengan $r$ jari-jari.")
    assert markup is None
    assert "^" not in spoken and "=" not in spoken
    assert issues


def test_teks_tanpa_dolar_tetapi_bersimbol_diganti_kata(verbalizer):
    spoken, markup, issues = speech.derive_message("Nilainya x^2 = 4.")
    assert markup is None and issues
    assert "^" not in spoken and "sama dengan" in spoken


@pytest.mark.parametrize("text", ["Sudut keliling sama dengan setengah sudut pusat.", "Jari-jari dan tali busur.", "Rp5.000 per buah."])
def test_teks_biasa_tanpa_simbol_tidak_berubah(verbalizer, text):
    assert speech.derive_message(text) == (text, None, [])


def test_bagian_di_luar_rumus_sama_pada_bacaan_dan_markup(verbalizer):
    text = "Pusatnya titik dengan koordinat $h$ dan $k$. Persamaannya $x = 1$."
    spoken, markup, _ = speech.derive_message(text)
    assert markup == text
    assert spoken == "Pusatnya titik dengan koordinat <h> dan <k>. Persamaannya <x = 1>."


@pytest.mark.parametrize("value", [None, 5, ["a"], {"x": 1}])
def test_clean_field_bukan_string_menjadi_kosong(value):
    assert speech.clean_field(value) == ""


def test_clean_field_membuang_dolar_dan_simbol_tetapi_mempertahankan_teks_biasa():
    assert speech.clean_field("Rumus $x^2$ dipakai.") == "Rumus x pangkat 2 dipakai."
    assert speech.clean_field("Lihat bab lingkaran.") == "Lihat bab lingkaran."


def finalize_raw(arguments, outputs=None):
    call = SimpleNamespace(function=SimpleNamespace(arguments=arguments))
    return agent._finalize(call, outputs or {"85": "sudut pusat dua kali sudut keliling"}, [], {"klass": "inti"})


def sources_json(**extra):
    return {"sources": [{"source_type": "modul", "label": "Bab $x$", "reference": "85", "evidence": "sudut pusat dua kali sudut keliling", "justification": "Rumus $x^2$ relevan"}], **extra}


@pytest.mark.parametrize("summary", [None, 5, ["a"], "", "   "])
def test_finalize_summary_kosong_atau_bukan_string_memakai_pesan_cadangan(verbalizer, summary):
    result = finalize_raw(json.dumps(sources_json(summary=summary)))
    assert result["message"] == agent.NO_SOURCE_FALLBACK


def test_finalize_membersihkan_label_justification_dan_pertanyaan_lanjutan(verbalizer):
    result = finalize_raw(json.dumps(sources_json(summary="Sudut pusat dua kali.", suggested_questions=["Apa itu $x^2$?", "Biasa saja?", 7])))
    assert result["sources"][0]["label"] == "Bab x"
    assert "$" not in result["sources"][0]["justification"]
    assert result["suggested_questions"] == ["Apa itu x pangkat 2?", "Biasa saja?"]


def test_finalize_daftar_pertanyaan_kosong_menjadi_none(verbalizer):
    result = finalize_raw(json.dumps(sources_json(summary="Sudut pusat dua kali.", suggested_questions=[])))
    assert result["suggested_questions"] is None


def test_run_semua_jalur_membawa_kunci_markup_dan_temuan(monkeypatch):
    monkeypatch.setattr(agent.scope_gate, "check_scope", lambda question, chunks: {"klass": "di_luar_topik"})
    result = agent.run("pertanyaan", [], lambda query: [])
    assert result["status"] == "out_of_scope"
    assert result["message_markup"] is None
    assert result["format_issues"] == []


@pytest.mark.parametrize("formula", ["90^", "x^", "a_", "(x^)", "{y_}"])
def test_pangkat_atau_subskrip_tanpa_isi_menghapus_markup(verbalizer, formula):
    spoken, markup, issues = speech.derive_message(f"Nilainya ${formula}$ derajat.")
    assert markup is None
    assert any("tanpa isi" in issue for issue in issues)


@pytest.mark.parametrize("formula", [r"90^\circ", "x^2", "a_1", "x^{10}"])
def test_pangkat_dan_subskrip_berisi_tidak_ditandai(verbalizer, formula):
    assert speech.derive_message(f"Nilainya ${formula}$ saja.")[1] is not None


def test_pasangan_rumus_unik_berurutan_dengan_bacaan_verbalizer(verbalizer):
    pairs = speech.formula_pairs("Pusat $P(a, b)$ dan persamaan $x^2 = 4$, lalu $P(a, b)$ lagi.")
    assert pairs == [{"latex": "P(a, b)", "bacaan": "<P(a, b)>"}, {"latex": "x^2 = 4", "bacaan": "<x^2 = 4>"}]


def test_teks_tanpa_rumus_tidak_menghasilkan_pasangan(verbalizer):
    assert speech.formula_pairs("Fungsi memetakan anggota domain.") == []
    assert verbalizer == []
