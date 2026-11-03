import pytest

from quizzer.stimulus import registry, tabel

TABLE = {"judul": "Nilai ujian", "kolom": ["Nama", "Skor"], "baris": [["Ani", "80"], ["Budi", "90,5"]]}


def test_tabel_valid_dan_teks_turunan_memuat_semua_sel_dan_ringkasan():
    assert tabel.validate(TABLE) == []
    narration = tabel.narrate(TABLE)
    assert "Ada 2 kolom" in narration.readable_text and "Baris 2." in narration.readable_text and "90,5" in narration.readable_text
    assert narration.tabel["kolom"] == ["Nama", "Skor"] and "2 baris data" in narration.ringkasan


@pytest.mark.parametrize(
    "data",
    [
        {**TABLE, "judul": ""}, {k: v for k, v in TABLE.items() if k != "judul"}, {**TABLE, "kolom": []}, {**TABLE, "baris": []},
        {**TABLE, "baris": [["Ani"]]}, {**TABLE, "baris": [["Ani", 80]]}, {**TABLE, "kolom": ["Nama", ""]}, {**TABLE, "baris": "x"},
    ],
)
def test_tabel_tidak_valid_ditolak(data):
    assert tabel.validate(data)


def test_tabel_lewat_registry_dengan_semua_jenis_aktif_dan_ditolak_saat_hanya_teks(monkeypatch):
    from quizzer import config

    stimulus = {"jenis": "tabel", "narasi": "Perhatikan data berikut.", "spesifikasi": TABLE}
    monkeypatch.setattr(config, "STIMULUS_TYPES", ("*",))
    assert registry.check(stimulus) == []
    result = registry.derive(stimulus, [])
    assert result["tabel"]["judul"] == "Nilai ujian" and result["readable_text"].startswith("Perhatikan data berikut.")
    monkeypatch.setattr(config, "STIMULUS_TYPES", ("teks",))
    assert "tidak tersedia" in registry.check(stimulus)[0]


def test_sel_tabel_boleh_memuat_latex_berpasangan_dan_dibacakan_dengan_kata(monkeypatch):
    from common import math_text

    monkeypatch.setattr(math_text, "convert_checked", lambda latex: (f"bacaan {len(latex)}", []))
    data = {"judul": "Rumus", "kolom": ["Nama", "Bentuk"], "baris": [["Pecahan", "$\\frac{1}{2}$"], ["Pangkat", "$x^{2}$"]]}
    assert tabel.validate(data) == []
    narration = tabel.narrate(data)
    assert "$" not in narration.readable_text and "\\" not in narration.readable_text
    assert data["baris"][0][1] == "$\\frac{1}{2}$"


@pytest.mark.parametrize(
    "cell",
    ["$x^{2", "harga $5", "<b>tebal</b>", "`kode`", "x" * 201],
)
def test_sel_tabel_dengan_latex_rusak_tag_atau_terlalu_panjang_ditolak(cell):
    assert tabel.validate({**TABLE, "baris": [["Ani", cell]]})


@pytest.mark.parametrize("cell", ["**tebal**", "# judul", "a | b", "kode`x`"])
def test_markdown_di_luar_latex_ditolak_tetapi_simbol_di_dalam_latex_boleh(cell):
    assert tabel.validate({**TABLE, "baris": [["Ani", cell]]})
    assert tabel.validate({**TABLE, "judul": cell})
    assert tabel.validate({**TABLE, "baris": [["Ani", "$a * b$"]]}) == []
