import pytest

from annoter import annoter_regenerate as regen

TABEL = {"judul": "Nilai", "kolom": ["x", "y"], "baris": [["1", "2"], ["3", "4"]]}


def test_edit_hanya_berlaku_untuk_blok_khusus():
    with pytest.raises(ValueError):
        regen.edit("text", readable_text="a")


@pytest.mark.parametrize("block_type", ["formula", "table", "image"])
def test_edit_tanpa_masukan_ditolak(block_type):
    with pytest.raises(ValueError):
        regen.edit(block_type)


def test_rumus_dari_sumber_diturunkan_lewat_verbalizer(monkeypatch):
    seen = []
    monkeypatch.setattr(regen.math_text, "readable_texts", lambda markups, issues=None: seen.append(markups) or ["x kuadrat"])
    result = regen.edit("formula", source_markup="x^{2}")
    assert result.text == "x kuadrat" and result.source_markup == "x^{2}" and seen == [["$x^{2}$"]]


def test_rumus_dengan_latex_rusak_ditolak():
    with pytest.raises(ValueError):
        regen.edit("formula", source_markup="$\\frac{a}{b$")


def test_readable_text_menimpa_turunan_dan_sumber_tetap_disimpan(monkeypatch):
    monkeypatch.setattr(regen.math_text, "readable_texts", lambda markups, issues=None: ["bacaan otomatis"])
    result = regen.edit("formula", readable_text="  x kuadrat  ", source_markup="x^{2}")
    assert result.text == "x kuadrat" and result.source_markup == "x^{2}"


def test_readable_text_dengan_notasi_mentah_ditolak():
    with pytest.raises(ValueError):
        regen.edit("formula", readable_text="x^2 sama dengan empat")


def test_tabel_diturunkan_ulang_beserta_ringkasan_dan_html():
    result = regen.edit("table", tabel=TABEL)
    assert "Ada 2 kolom" in result.text and "Baris 1" in result.text
    assert result.ringkasan and result.tabel["kolom"] == ["x", "y"] and "<table" in result.source_markup


def test_tabel_tidak_valid_ditolak():
    with pytest.raises(ValueError):
        regen.edit("table", tabel={"judul": "t", "kolom": ["a", "b"], "baris": [["1"]]})


def test_tabel_dengan_readable_text_memakai_teks_guru_dan_struktur_baru():
    result = regen.edit("table", tabel=TABEL, readable_text="Tabel dua kolom tentang nilai.")
    assert result.text == "Tabel dua kolom tentang nilai." and result.tabel is not None


def test_gambar_hanya_menerima_readable_text():
    assert regen.edit("image", readable_text="Grafik naik dari kiri ke kanan.").text == "Grafik naik dari kiri ke kanan."
    with pytest.raises(ValueError):
        regen.edit("image", readable_text="**tebal**")


def test_tabel_kosong_atau_tanpa_kunci_menjadi_valueerror_bukan_keyerror():
    for bad in ({}, {"judul": "t"}, {"kolom": ["a"]}):
        with pytest.raises(ValueError):
            regen.edit("table", tabel=bad)


def test_sel_tabel_dengan_notasi_mentah_ditolak():
    with pytest.raises(ValueError):
        regen.edit("table", tabel={"judul": "t", "kolom": ["x", "y"], "baris": [["x=3", "2"]]})


def test_readable_text_dikirim_tidak_memanggil_verbalizer_dan_tetap_memvalidasi_latex(monkeypatch):
    monkeypatch.setattr(regen.math_text, "readable_texts", lambda *args, **kwargs: pytest.fail("tidak boleh diverbalisasi"))
    result = regen.edit("formula", readable_text="x kuadrat", source_markup="x^{2}")
    assert result.issues == [] and result.source_markup == "x^{2}"
    with pytest.raises(ValueError):
        regen.edit("formula", readable_text="x kuadrat", source_markup="$\\frac{a}{b$")


def test_bacaan_tabel_diganti_tanpa_tabel_baru_diberi_peringatan():
    result = regen.edit("table", readable_text="Tabel dua kolom.")
    assert result.tabel is None and result.issues
