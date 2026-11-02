import pytest

from common import math_text

TABLE = {"judul": "Data", "kolom": ["x", "$f(x)$"], "baris": [["1", "2"], ["", "4"]]}


@pytest.fixture(autouse=True)
def stub_convert(monkeypatch):
    monkeypatch.setattr(math_text, "convert_checked", lambda latex: ("RUMUS(" + latex.strip() + ")", []))


def test_split_math_memisahkan_teks_dan_rumus_satu_dua_dolar():
    assert math_text.split_math("a $x^2$ b $$y$$ c") == [
        (False, "a "), (True, "x^2"), (False, " b "), (True, "y"), (False, " c"),
    ]


def test_readable_texts_mengganti_rumus_dan_merapikan_spasi_sebelum_tanda_baca():
    texts = ["Nilai $f(x)$ adalah $2$ , ya.", "polos"]
    assert math_text.readable_texts(texts) == ["Nilai RUMUS(f(x)) adalah RUMUS(2), ya.", "polos"]


def test_latex_issues_kosong_untuk_rumus_benar():
    assert math_text.latex_issues("benar $a+b$") == []


@pytest.mark.parametrize(
    "markup",
    ["rusak $a+b", r"$\frac{1}{2$", r"$\left( x$", "$$ $$"],
)
def test_latex_issues_melaporkan_markup_rusak(markup):
    assert math_text.latex_issues(markup)


def test_split_table_memulihkan_teks_dan_tabel_dari_table_html():
    text, parsed = math_text.split_table("Perhatikan data. " + math_text.table_html(TABLE))
    assert text == "Perhatikan data."
    assert parsed == TABLE


def test_split_table_tanpa_tabel_mengembalikan_teks_apa_adanya():
    assert math_text.split_table("tanpa tabel") == ("tanpa tabel", None)


def test_split_table_tanpa_header_th_menghasilkan_tabel_none():
    assert math_text.split_table("<table><tr><td>x</td></tr></table>")[1] is None


def test_table_readable_menyebut_kolom_lalu_baris_dengan_sel_kosong():
    text = math_text.table_readable(math_text.spoken_table(TABLE))
    assert text == (
        "Tabel Data. Ada 2 kolom: x dan RUMUS(f(x)). "
        "Baris 1. x: 1; RUMUS(f(x)): 2. Baris 2. x: kosong; RUMUS(f(x)): 4."
    )


def test_table_issues_kosong_untuk_tabel_benar():
    assert math_text.table_issues(TABLE) == []


@pytest.mark.parametrize(
    "table",
    ["x", {"kolom": ["a"], "baris": [["1", "2"]]}, {"kolom": [], "baris": []}],
)
def test_table_issues_melaporkan_tabel_tidak_valid(table):
    assert math_text.table_issues(table)


def test_table_summary_menyebut_semua_kolom_bila_sedikit():
    spoken = math_text.spoken_table({"judul": "Harga", "kolom": ["Buah", "Harga", "Stok"], "baris": [["a", "1", "2"]]})
    assert math_text.table_summary(spoken) == (
        "Tabel Harga. Ada 3 kolom dan 1 baris data. Nama kolomnya adalah Buah, Harga, dan Stok."
    )


def test_table_summary_meringkas_kolom_berlebih_dan_judul_kosong():
    spoken = math_text.spoken_table({"judul": None, "kolom": [f"k{i}" for i in range(9)], "baris": [["1"] * 9]})
    summary = math_text.table_summary(spoken)
    assert "3 kolom lainnya" in summary
    assert summary.startswith("Tabel tanpa judul.")


def test_table_summary_tidak_menambah_kata_tabel_bila_judul_sudah_diawali_tabel():
    spoken = math_text.spoken_table({"judul": "Tabel 1.1 Nilai.", "kolom": ["x"], "baris": [["1"], ["2"]]})
    assert math_text.table_summary(spoken).startswith("Tabel 1.1 Nilai. Ada 1 kolom dan 2 baris")


def test_spoken_table_mengeja_huruf_yunani_dan_mengisi_sel_none_dengan_kosong():
    spoken = math_text.spoken_table({"judul": None, "kolom": ["(α)", "b"], "baris": [[None, "α."]]})
    assert spoken["kolom"] == ["(alfa)", "b"]
    assert spoken["baris"] == [["kosong", "alfa."]]


def test_table_html_tidak_menulis_none_untuk_sel_kosong():
    assert "None" not in math_text.table_html({"judul": None, "kolom": ["a"], "baris": [[None]]})


@pytest.mark.parametrize(
    "text, expected",
    [("sudut alpha", "sudut alfa"), ("Theta dan phi", "teta dan fi"), ("α dan θ", "alfa dan teta"), ("alphabet", "alphabet")],
)
def test_spell_greek_menyeragamkan_nama_inggris_dan_simbol(text, expected):
    assert math_text.spell_greek(text) == expected


@pytest.mark.parametrize("text, expected", [("sudut Θ", "sudut teta"), ("ξ dan ϕ", "ksi dan fi"), ("ϑ", "teta")])
def test_spell_greek_mencakup_huruf_yunani_tambahan(text, expected):
    assert math_text.spell_greek(text) == expected


def test_readable_texts_membuang_titik_ganda_bila_teks_sudah_menyebut_titik(monkeypatch):
    monkeypatch.setattr(math_text, "convert_checked", lambda latex: ("titik A dengan koordinat dua dan lima", []))
    assert math_text.readable_texts(["Titik $A(2, 5)$ ada."]) == ["Titik A dengan koordinat dua dan lima ada."]
    assert math_text.readable_texts(["Lihat $A(2, 5)$."]) == ["Lihat titik A dengan koordinat dua dan lima."]


def test_readable_texts_mengeja_huruf_yunani_di_teks_polos():
    assert math_text.readable_texts(["Sudut θ dan alpha"]) == ["Sudut teta dan alfa"]


def test_table_summary_menyeragamkan_huruf_yunani_pada_topik():
    spoken = {"judul": None, "kolom": ["a"], "baris": [["1"]]}
    assert math_text.table_summary(spoken, "Nilai theta").startswith("Nilai teta.")


def test_strip_tags_hanya_membuang_tag_html_sungguhan():
    assert math_text.strip_tags("Jika x < 5 dan y > 3 maka benar.") == "Jika x < 5 dan y > 3 maka benar."
    assert math_text.strip_tags("Isi <b>tebal</b> dan <sup>2</sup>.") == "Isi tebal dan 2."
    assert math_text.strip_tags("<br/>a") == "a"
    assert math_text.strip_tags("a<td>b", " ") == "a b"

