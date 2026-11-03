import pytest

from common import svg_raster
from quizzer import config, quizzer_regenerate
from quizzer.stimulus import gambar, registry

pytestmark = pytest.mark.usefixtures("fake_vision")

BLOCKS = [{"reading_order": i * 10, "block_type": "text", "readable_text": f"blok {i}"} for i in range(10)]
SVG = '<svg viewBox="0 0 100 50"><rect x="5" y="5" width="20" height="20"/><text x="5" y="40">30</text></svg>'
TABLE = {"judul": "Nilai", "kolom": ["bulan", "jumlah"], "baris": [["Januari", "30"], ["Februari", "50"]]}
SOAL = [
    {"id": 1, "question_text": "q", "options": {}, "correct_option": "A", "langkah": ["l"], "kesimpulan": "k", "markup": None},
    {"id": 2, "question_text": "q2", "options": {}, "correct_option": "B", "langkah": ["l"], "kesimpulan": "k", "markup": None},
]


@pytest.fixture(autouse=True)
def types_and_review(monkeypatch):
    monkeypatch.setattr(config, "STIMULUS_TYPES", ("*",))
    seen = []

    def review(source, data, stimulus_text=""):
        seen.append((data["id"], stimulus_text))
        return ["Opsi B juga benar."] if data["id"] == 2 else []

    monkeypatch.setattr(quizzer_regenerate, "review_soal", review)
    return seen


def run(stimulus, edit):
    return quizzer_regenerate.compute_stimulus_edit(BLOCKS, 0, 50, stimulus, SOAL, edit)


def test_stimulus_teks_diturunkan_dari_sumber_dan_seluruh_cluster_diverifikasi(types_and_review):
    result = run({"jenis": "teks", "readable_text": "lama"}, {"source_markup": "Harga naik dari tiga ribu menjadi lima ribu."})
    assert result["new_stimulus"]["readable_text"] == "Harga naik dari tiga ribu menjadi lima ribu."
    assert result["soal_issues"] == {1: [], 2: ["Opsi B juga benar."]}
    assert sorted(item[0] for item in types_and_review) == [1, 2]


@pytest.mark.parametrize("markup", ["", "   ", "Nilai **tebal**", "Rumus $\\frac{a}{b$ rusak", "x = 2 + 3"])
def test_stimulus_teks_tidak_valid_ditolak(markup):
    with pytest.raises(ValueError):
        run({"jenis": "teks", "readable_text": "lama"}, {"source_markup": markup})


def test_stimulus_tabel_diturunkan_dari_sel_dan_narasi_lama_dipertahankan():
    stored = registry.derive({"jenis": "tabel", "narasi": "Perhatikan data bulanan.", "spesifikasi": TABLE})
    assert registry.current_narasi(stored) == "Perhatikan data bulanan."
    edited = {**TABLE, "baris": [["Januari", "30"], ["Februari", "70"]]}
    text = run(stored, {"spesifikasi": edited})["new_stimulus"]["readable_text"]
    assert text.startswith("Perhatikan data bulanan.") and "70" in text


def test_narasi_baru_menggantikan_yang_lama_dan_narasi_kosong_menghapusnya():
    stored = registry.derive({"jenis": "tabel", "narasi": "Perhatikan data bulanan.", "spesifikasi": TABLE})
    assert run(stored, {"narasi": "Data penjualan.", "spesifikasi": TABLE})["new_stimulus"]["readable_text"].startswith("Data penjualan.")
    assert run(stored, {"narasi": "", "spesifikasi": TABLE})["new_stimulus"]["readable_text"].startswith("Tabel")


def test_spesifikasi_tabel_tidak_valid_ditolak():
    stored = registry.derive({"jenis": "tabel", "narasi": "", "spesifikasi": TABLE})
    with pytest.raises(ValueError):
        run(stored, {"spesifikasi": {"judul": "x", "kolom": ["a"], "baris": [["1", "2"]]}})


def test_stimulus_gambar_diturunkan_ulang_lewat_vision(fake_vision):
    stored = registry.derive({"jenis": "gambar", "narasi": "Perhatikan gambar.", "spesifikasi": {"svg": SVG}})
    result = run(stored, {"spesifikasi": {"svg": SVG.replace("30", "50")}})
    assert result["new_stimulus"]["jenis"] == "gambar" and "Perhatikan gambar." in result["new_stimulus"]["readable_text"]
    assert len(fake_vision) == 2


def test_gambar_tidak_bisa_dirender_menjadi_valueerror(monkeypatch):
    stored = registry.derive({"jenis": "gambar", "narasi": "", "spesifikasi": {"svg": SVG}})

    def fail(svg, context, feedback=""):
        raise svg_raster.RenderError("path rusak")

    monkeypatch.setattr(gambar, "_render_and_describe", fail)
    with pytest.raises(ValueError, match="tidak dapat dirender"):
        run(stored, {"spesifikasi": {"svg": SVG}})


def test_verifikasi_yang_melempar_menjadi_penanda_bukan_kegagalan(monkeypatch):
    def broken(source, data, stimulus_text=""):
        raise RuntimeError("validator mati")

    monkeypatch.setattr(quizzer_regenerate, "review_soal", broken)
    result = run({"jenis": "teks", "readable_text": "lama"}, {"source_markup": "Teks baru."})
    assert all("manual" in issues[0] for issues in result["soal_issues"].values())


def test_narasi_lama_yang_tidak_bisa_dipulihkan_ditandai_bukan_dibuang_diam_diam():
    stored = registry.derive({"jenis": "tabel", "narasi": "Perhatikan data bulanan.", "spesifikasi": TABLE})
    broken = {**stored, "readable_text": "Teks yang tidak berakhir dengan bacaan tabel."}
    assert registry.current_narasi(broken) is None
    result = run(broken, {"spesifikasi": TABLE})
    assert any("Narasi pengantar lama" in issue for issue in result["soal_issues"][1])


def test_narasi_kosong_yang_sah_tidak_ditandai():
    stored = registry.derive({"jenis": "tabel", "narasi": "", "spesifikasi": TABLE})
    assert registry.current_narasi(stored) is None or registry.current_narasi(stored) == ""
    result = run(stored, {"narasi": "", "spesifikasi": TABLE})
    assert not any("Narasi pengantar lama" in issue for issue in result["soal_issues"][1])


@pytest.mark.parametrize("cell", ["x=3", "a<b", "50 ÷ 2", "**tebal**"])
def test_sel_tabel_stimulus_dengan_notasi_mentah_ditolak(cell):
    stored = registry.derive({"jenis": "tabel", "narasi": "", "spesifikasi": TABLE})
    with pytest.raises(ValueError):
        run(stored, {"spesifikasi": {**TABLE, "baris": [["Januari", cell]]}})


def test_sel_tabel_dengan_rumus_dalam_dolar_diterima(monkeypatch):
    from common import math_text

    monkeypatch.setattr(math_text, "readable_texts", lambda markups, issues=None: [m.replace("$", "") for m in markups])
    stored = registry.derive({"jenis": "tabel", "narasi": "", "spesifikasi": TABLE})
    result = run(stored, {"spesifikasi": {**TABLE, "baris": [["Januari", "$x^{2}$"]]}})
    assert result["new_stimulus"]["jenis"] == "tabel"
