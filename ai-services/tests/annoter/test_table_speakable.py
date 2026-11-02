import pytest

from annoter import table
from common import math_text


@pytest.fixture(autouse=True)
def stub_convert(monkeypatch):
    monkeypatch.setattr(math_text, "convert_checked", lambda latex: (latex, []))


def build(columns, rows, judul="Data"):
    data = {"pengamatan": {"judul": judul, "kolom": columns, "baris": rows}, "deskripsi": "d", "topik": "Tabel ini tentang data."}
    return table.from_response(data, "", compare_ocr=False)


def test_satuan_ber_garis_miring_pada_judul_kolom_dibaca_per():
    result = build(["Waktu (menit)", "Kecepatan (km/jam)"], [["1", "100"]])
    assert result.tabel["kolom"] == ["Waktu (menit)", "Kecepatan (kilometer per jam)"]
    assert "kilometer per jam" in result.text and "/" not in result.text


def test_sel_negatif_dan_elipsis_dibacakan_dengan_aturan_yang_sama():
    result = build(["x", "y"], [["-3", "..."], ["10-19", "dan/atau"]])
    assert result.tabel["baris"] == [["minus 3", "..."], ["10-19", "dan atau"]]


def test_tabel_tanpa_judul_tetap_none():
    assert build(["a"], [["1"]], judul="").tabel["judul"] is None
