import pytest

from quizzer import config
from quizzer.stimulus import registry

SVG = '<svg viewBox="0 0 100 60"><rect x="10" y="10" width="30" height="40" fill="gray"/><text x="10" y="58">30</text></svg>'
IMAGE = {"svg": SVG}
TABLE = {"judul": "Nilai", "kolom": ["Nama", "Skor"], "baris": [["Ani", "80"], ["Budi", "90"]]}


@pytest.fixture(autouse=True)
def all_types(monkeypatch, fake_vision):
    monkeypatch.setattr(config, "STIMULUS_TYPES", ("*",))


def stimulus(*components, narasi="Perhatikan data berikut."):
    return {"jenis": "campuran", "narasi": narasi, "spesifikasi": {"komponen": list(components)}}


def test_campuran_teks_tabel_dan_gambar_valid_dan_berurutan():
    data = stimulus({"jenis": "teks", "teks": "Sebuah toko mencatat penjualan."}, {"jenis": "tabel", "tabel": TABLE}, {"jenis": "gambar", "spesifikasi": IMAGE})
    assert registry.check(data) == []
    result = registry.derive(data)
    text = result["readable_text"]
    assert text.index("Perhatikan") < text.index("Sebuah toko") < text.index("Ada 2 kolom") < text.index("Diagram batang")
    assert result["tabel"] is not None and result["jenis"] == "campuran"
    assert result["spesifikasi"]["komponen"][2]["spesifikasi"]["svg"].startswith("<svg")


def test_campuran_menolak_komponen_tidak_valid():
    bad = [
        {"jenis": "teks", "teks": ""}, {"jenis": "teks", "teks": "rumus $x"}, {"jenis": "tabel", "tabel": {"kolom": [], "baris": []}}, {"jenis": "campuran", "spesifikasi": {"komponen": []}},
        {"jenis": "gambar", "spesifikasi": {"svg": "<svg></svg>"}}, {"jenis": "tidak_ada", "spesifikasi": {}}, "teks", {"jenis": "teks", "teks": "a", "x": 1},
        {"jenis": "gambar", "spesifikasi": {**IMAGE, "tambahan": 1}}, {"jenis": "gambar", "spesifikasi": {"svg": "<script/>"}},
    ]
    for component in bad:
        assert registry.check(stimulus(component)), component


def test_campuran_menolak_kosong_dan_terlalu_banyak_komponen():
    assert registry.check({"jenis": "campuran", "spesifikasi": {"komponen": []}})
    assert registry.check({"jenis": "campuran", "spesifikasi": {"komponen": [{"jenis": "teks", "teks": "a"}] * 13}})
    assert registry.check({"jenis": "campuran", "spesifikasi": {"komponen": "teks"}})


def test_campuran_hanya_menerima_jenis_yang_aktif(monkeypatch):
    monkeypatch.setattr(config, "STIMULUS_TYPES", ("campuran",))
    assert "tidak tersedia" in registry.check(stimulus({"jenis": "gambar", "spesifikasi": IMAGE}))[0]
    assert registry.check(stimulus({"jenis": "teks", "teks": "Cukup teks."})) == []


def test_campuran_tidak_menerima_campuran_bersarang():
    nested = {"jenis": "campuran", "spesifikasi": {"komponen": [{"jenis": "teks", "teks": "a"}]}}
    assert registry.check(stimulus(nested))


def test_campuran_menambah_titik_di_akhir_tiap_komponen_tanpa_menggabung_kalimat():
    data = stimulus({"jenis": "teks", "teks": "Data toko"}, {"jenis": "teks", "teks": "Hitung selisihnya."}, narasi="")
    assert registry.derive(data)["readable_text"] == "Data toko. Hitung selisihnya."


def test_campuran_memanggil_deskriptor_hanya_untuk_komponen_gambar(fake_vision):
    data = stimulus({"jenis": "teks", "teks": "Data toko."}, {"jenis": "gambar", "spesifikasi": IMAGE}, {"jenis": "gambar", "spesifikasi": IMAGE})
    result = registry.derive(data, [])
    assert len(fake_vision) == 2
    assert all(component["spesifikasi"]["deskripsi"] for component in result["spesifikasi"]["komponen"] if component["jenis"] == "gambar")


def test_editable_spec_campuran_membuang_kunci_turunan_di_komponen():
    derived = registry.derive(stimulus({"jenis": "gambar", "spesifikasi": IMAGE}), [])["spesifikasi"]
    derived["komponen"][0]["spesifikasi"]["turunan"] = 1
    editable = registry.editable_spec("campuran", derived)
    assert "turunan" not in editable["komponen"][0]["spesifikasi"]
    assert registry.check({"jenis": "campuran", "narasi": "", "spesifikasi": editable}) == []


def test_latex_pada_narasi_dan_teks_komponen_diterima_dan_dibacakan_dengan_kata(monkeypatch):
    from common import math_text

    monkeypatch.setattr(math_text, "convert_checked", lambda latex: ("x kuadrat" if "2" in latex else "x", []))
    data = stimulus({"jenis": "teks", "teks": "Fungsi $x^{2}$ diberikan."}, narasi="Perhatikan $x$ berikut.")
    assert registry.check(data) == []
    result = registry.derive(data, [])
    assert result["readable_text"] == "Perhatikan x berikut. Fungsi x kuadrat diberikan."
    assert result["source_markup"] == "Perhatikan $x$ berikut."
    assert result["spesifikasi"]["komponen"][0]["teks"] == "Fungsi $x^{2}$ diberikan."


@pytest.mark.parametrize("narasi", ["Nilai x = 5.", "Naik 50%.", "<b>tebal</b> teks", "Rumus $x belum berpasangan."])
def test_narasi_dengan_simbol_markup_atau_latex_rusak_di_luar_rumus_ditolak(narasi):
    assert registry.check(stimulus({"jenis": "teks", "teks": "a"}, narasi=narasi))
