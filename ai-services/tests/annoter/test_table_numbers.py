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


def response(rows, judul="Harga"):
    return {
        "pengamatan": {"judul": judul, "kolom": ["Buah", "Harga"], "baris": rows},
        "deskripsi": "d",
        "topik": "Tabel ini tentang harga buah.",
    }


def dropped(data, ocr=OCR, compare_ocr=True):
    return [issue for issue in table.from_response(data, ocr, compare_ocr).issues if "angka di hasil OCR" in issue]


def test_angka_ocr_yang_hilang_dari_sel_menambah_issue():
    assert dropped(response([["Apel", "7"], ["Jeruk", ""]]))


def test_angka_sama_dengan_ocr_tidak_menambah_issue():
    assert not dropped(response([["Apel", "5"], ["Jeruk", ""]]))


def test_model_mengisi_sel_yang_kosong_di_ocr_tidak_menambah_issue():
    assert not dropped(response([["Apel", "5"], ["Jeruk", "8"]]))


def test_regenerasi_tidak_membandingkan_dengan_ocr():
    assert not dropped(response([["Apel", "7"], ["Jeruk", ""]]), compare_ocr=False)


def test_pemisah_ribuan_dan_angka_judul_tidak_memicu_perbedaan():
    ocr = "<table><tr><td>Jumlah</td><td>Harga</td></tr><tr><td>1</td><td>55.000</td></tr></table>"
    assert not dropped(response([["1", "55000"]], judul="Tabel 1.1"), ocr)


def test_daftar_angka_berkoma_dengan_dan_tanpa_spasi_sama():
    ocr = "<table><tr><td>Data</td></tr><tr><td>1,2,3</td></tr></table>"
    assert not dropped({"pengamatan": {"judul": "", "kolom": ["Data"], "baris": [["1, 2, 3"]]}, "deskripsi": "d", "topik": "Tabel ini tentang data."}, ocr)


def test_entitas_html_dan_atribut_tidak_dihitung_sebagai_angka():
    ocr = "<table><tr><td rowspan=1 colspan=1>Buah</td><td>Harga</td></tr><tr><td>Apel</td><td>5&#160;</td></tr></table>"
    assert not dropped(response([["Apel", "5"]]), ocr)


def test_tanda_lebih_kecil_literal_di_sel_ocr_tidak_menelan_angka():
    ocr = "<table><tr><td>Syarat</td></tr><tr><td>x < 5</td></tr></table>"
    data = {"pengamatan": {"judul": "", "kolom": ["Syarat"], "baris": [["x < 5"]]}, "deskripsi": "d", "topik": "Tabel ini tentang syarat."}
    assert not dropped(data, ocr)
    assert dropped({"pengamatan": {"judul": "", "kolom": ["Syarat"], "baris": [["x < 7"]]}, "deskripsi": "d", "topik": "Tabel ini tentang syarat."}, ocr)


def test_ocr_tanpa_angka_tidak_memicu_perbedaan():
    ocr = "<table><tr><td>Buah</td><td>Harga</td></tr></table>"
    assert not dropped(response([["Apel", "5"]]), ocr)
