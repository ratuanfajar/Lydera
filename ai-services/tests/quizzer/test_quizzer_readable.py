import random

import pytest

from common import math_text
from quizzer import checks, readable, shuffle


@pytest.fixture(autouse=True)
def stub_convert(monkeypatch):
    monkeypatch.setattr(math_text, "convert_checked", lambda latex: ("r" + "".join(c for c in latex if c.isalnum()), []))


@pytest.fixture
def raw():
    return {
        "question_text": "Berapa $f(2)$ jika $f(x) = 2x + 1$?",
        "options": {"A": "$5$", "B": "$4$", "C": "$3$", "D": "$6$"},
        "correct_option": "A",
        "langkah": ["Ganti x dengan 2: $f(2) = 5$.", "Jadi opsi A benar."],
        "kesimpulan": "Jawabannya $5$ (opsi A).",
        "stimulus": {
            "readable_text": "Data penjualan: $x$ barang.",
            "tabel": {"judul": "Harga", "kolom": ["x", "$y$"], "baris": [["1", "2"]]},
        },
    }


@pytest.fixture
def plain():
    return {
        "question_text": "Apa itu fungsi?", "options": {"A": "a", "B": "b", "C": "c", "D": "d"}, "correct_option": "A",
        "langkah": ["x"], "kesimpulan": "k", "stimulus": None,
    }


def test_markup_issues_kosong_untuk_markup_benar(raw):
    assert readable.markup_issues(raw) == []


def test_markup_issues_melaporkan_latex_rusak_dan_tabel_tidak_valid(raw):
    bad = dict(raw, question_text="Hitung $x^{2$", stimulus={"readable_text": "t", "tabel": {"kolom": ["a"], "baris": [["1", "2"]]}})
    assert len(readable.markup_issues(bad)) == 2


def test_derive_mengubah_soal_dan_opsi_menjadi_bacaan_dan_menyimpan_markup(raw):
    data, _ = readable.derive(raw)
    assert data["question_text"] == "Berapa rf2 jika rfx2x1?"
    assert data["options"]["A"] == "r5"
    assert data["markup"]["options"]["A"] == "$5$"


def test_derive_menurunkan_stimulus_tabel_menjadi_bacaan_dan_html(raw):
    data, _ = readable.derive(raw)
    assert "Tabel Harga." in data["stimulus"]["readable_text"]
    assert "<table>" in data["stimulus"]["source_markup"]


def test_derive_menghasilkan_soal_yang_lolos_code_issues(raw):
    data, _ = readable.derive(raw)
    assert checks.code_issues(data, 4) == []


def test_derive_soal_tanpa_rumus_tidak_membuat_markup(plain):
    data, _ = readable.derive(plain)
    assert data["markup"] is None
    assert data["question_text"] == "Apa itu fungsi?"
    assert data["stimulus"] is None


def test_reorder_options_setelah_derive_menggeser_kunci_dan_markup_serta_huruf_rujukan(raw):
    data, _ = readable.derive(raw)
    data = shuffle.reorder_options(data, "C", random.Random(1))
    assert data["correct_option"] == "C"
    assert data["options"]["C"] == "r5"
    assert data["markup"]["options"]["C"] == "$5$"
    assert "opsi C" in data["langkah"][1]
    assert "opsi C" in data["markup"]["langkah"][1]
    assert "opsi C" in data["kesimpulan"]


@pytest.fixture
def fields():
    return {"question": "Nilai $x$?", "options": {"A": "1", "B": "2", "C": "3", "D": "4"}, "langkah": ["l"], "kesimpulan": "k"}


def test_derive_fields_dengan_rumus_mengembalikan_bacaan_dan_markup_asli(fields):
    spoken, markup = readable.derive_fields(fields)
    assert spoken["question"] == "Nilai rx?"
    assert markup is fields


def test_derive_fields_tanpa_rumus_mengembalikan_markup_none(fields):
    _, markup = readable.derive_fields(dict(fields, question="Nilai x?"))
    assert markup is None


def test_derive_stimulus_teks_biasa_tanpa_markup():
    reading = readable.derive_stimulus("Cerita biasa.")
    assert (reading.readable_text, reading.source_markup, reading.ringkasan, reading.tabel) == ("Cerita biasa.", None, None, None)


def test_derive_stimulus_dengan_rumus_menyimpan_markup_tanpa_ringkasan():
    reading = readable.derive_stimulus("Nilai $x$ adalah satu.")
    assert reading.source_markup
    assert reading.ringkasan is None


def test_derive_stimulus_dengan_tabel_html_menghasilkan_ringkasan_dan_baris():
    markup = "Data berikut. " + math_text.table_html({"judul": "T", "kolom": ["x", "y"], "baris": [["1", "2"]]})
    reading = readable.derive_stimulus(markup)
    assert reading.source_markup == markup
    assert reading.ringkasan == "Tabel T. Ada 2 kolom dan 1 baris data. Nama kolomnya adalah x dan y."
    assert reading.tabel == {"judul": "T", "kolom": ["x", "y"], "baris": [["1", "2"]]}
    assert "Baris 1. x: 1; y: 2." in reading.readable_text


def test_derive_stimulus_menolak_tabel_html_tak_terparse():
    with pytest.raises(ValueError):
        readable.derive_stimulus("<table><tr><td>x</td></tr></table>")
