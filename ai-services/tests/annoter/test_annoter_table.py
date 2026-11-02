import pytest

from annoter import table
from common import math_text

OCR = (
    "<table><tr><td>Buah</td><td>Harga</td></tr><tr><td>Apel</td><td>5</td></tr>"
    "<tr><td>Jeruk</td><td></td></tr></table>"
)


@pytest.fixture(autouse=True)
def stub_convert(monkeypatch):
    monkeypatch.setattr(math_text, "convert_checked", lambda latex: (latex, []))


@pytest.fixture
def good():
    return {
        "pengamatan": {"judul": "Harga", "kolom": ["Buah", "Harga"], "baris": [["Apel", "5"], ["Jeruk", ""]]},
        "deskripsi": "ignored",
        "topik": "Tabel ini tentang harga buah.",
    }


def observed(good, **parts):
    return dict(good, pengamatan=parts)


def test_from_response_membentuk_tabel_dengan_sel_kosong_menjadi_kosong(good):
    result = table.from_response(good, OCR)
    assert result.tabel == {"judul": "Harga", "kolom": ["Buah", "Harga"], "baris": [["Apel", "5"], ["Jeruk", "kosong"]]}
    assert result.issues == []


def test_from_response_menulis_teks_baca_per_baris(good):
    assert table.from_response(good, OCR).text == (
        "Tabel Harga. Ada 2 kolom: Buah dan Harga. Baris 1. Buah: Apel; Harga: 5. Baris 2. Buah: Jeruk; Harga: kosong."
    )


def test_from_response_ringkasan_memakai_topik_model(good):
    assert table.from_response(good, OCR).ringkasan == (
        "Tabel ini tentang harga buah. Ada 2 kolom dan 2 baris data. Nama kolomnya adalah Buah dan Harga."
    )


def test_from_response_tanpa_topik_ringkasan_memakai_judul(good):
    result = table.from_response(dict(good, topik=""), OCR)
    assert result.ringkasan.startswith("Tabel Harga. Ada 2 kolom dan 2 baris data.")


def test_from_response_topik_tanpa_titik_diberi_titik(good):
    result = table.from_response(dict(good, topik="Tabel ini tentang nilai"), OCR)
    assert result.ringkasan.startswith("Tabel ini tentang nilai. Ada 2 kolom")


def test_from_response_struktur_rusak_memakai_deskripsi_cadangan(good):
    bad = observed(good, kolom=["a", "b"], baris=[["1"]])
    result = table.from_response(dict(bad, deskripsi="Bacaan cadangan lengkap."), OCR)
    assert result.tabel is None
    assert result.text == "Bacaan cadangan lengkap."
    assert any("Struktur" in issue for issue in result.issues)


def test_from_response_pengamatan_kosong_melaporkan_masalah(good):
    result = table.from_response(observed(good), OCR)
    assert result.tabel is None
    assert result.issues


def test_from_response_ukuran_beda_dari_ocr_dilaporkan(good):
    result = table.from_response(observed(good, kolom=["a", "b", "c"], baris=[["1", "2", "3"]]), OCR)
    assert result.tabel
    assert any("OCR" in issue for issue in result.issues)


def test_from_response_colspan_ocr_dihitung_dan_kolom_kembar_dibedakan(good):
    colspan = "<table><tr><th colspan=2>A</th><th>B</th></tr><tr><td>1</td><td>2</td><td>3</td></tr></table>"
    result = table.from_response(observed(good, kolom=["A", "A", "B"], baris=[["1", "2", "3"]]), colspan)
    assert not any("OCR" in issue for issue in result.issues)
    assert result.tabel["kolom"] == ["A (kolom 1)", "A (kolom 2)", "B"]


def test_from_response_ocr_dengan_baris_judul_tambahan_tidak_dilaporkan(good):
    wide = "<table><tr><td>A</td></tr><tr><td>B</td></tr><tr><td>1</td></tr></table>"
    result = table.from_response(observed(good, kolom=["A"], baris=[["1"]]), wide)
    assert not any("OCR" in issue for issue in result.issues)


def test_from_response_sel_none_menjadi_kosong(good):
    result = table.from_response(observed(good, kolom=["a", "b"], baris=[["1", None]]), "")
    assert result.tabel["baris"] == [["1", "kosong"]]


def test_from_response_mengeja_huruf_yunani_dan_menamai_kolom_kosong(good):
    result = table.from_response(observed(good, kolom=["α", ""], baris=[["30°", "θ = 2"]]), "")
    assert result.tabel["kolom"] == ["alfa", "Kolom 2"]
    assert result.tabel["baris"] == [["30°", "teta = 2"]]


def test_from_response_latex_rusak_di_sel_dilaporkan(good):
    result = table.from_response(observed(good, kolom=["x", "y"], baris=[["1", "$x^{2$"]]), "")
    assert any("kurawal" in issue for issue in result.issues)


@pytest.mark.parametrize("topic", ["**x**", "x" * 300])
def test_topic_issues_melaporkan_markdown_dan_topik_panjang(topic):
    assert table.topic_issues(topic)


def test_topic_issues_kosong_untuk_satu_kalimat_biasa():
    assert table.topic_issues("Tabel ini tentang harga.") == []


def test_sel_tidak_terbaca_menandai_issue():
    data = {"pengamatan": {"judul": "", "kolom": ["a", "b"], "baris": [["1", "tidak terbaca"]]}, "deskripsi": "d", "topik": "Tabel ini tentang data."}
    result = table.from_response(data, "")
    assert any("tidak terbaca" in issue for issue in result.issues)


@pytest.mark.parametrize("title", ["tidak ada", "Tanpa judul", "-", None, ""])
def test_judul_penanda_kosong_menjadi_tanpa_judul(title):
    data = {"pengamatan": {"judul": title, "kolom": ["a"], "baris": [["1"]]}, "deskripsi": "d", "topik": "Tabel ini tentang data."}
    assert table.from_response(data, "").tabel["judul"] is None


def test_judul_sah_yang_memuat_penanda_tetap_utuh():
    data = {"pengamatan": {"judul": "Tidak ada kelulusan", "kolom": ["a"], "baris": [["1"]]}, "deskripsi": "d", "topik": "Tabel ini tentang data."}
    assert table.from_response(data, "").tabel["judul"] == "Tidak ada kelulusan"
