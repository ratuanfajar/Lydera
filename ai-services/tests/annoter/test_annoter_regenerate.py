import pytest

from annoter import annoter_regenerate
from common import formula

VEC = chr(92) + "vec{a}"


def test_regenerasi_rumus_koordinat_memakai_aturan_koordinat(monkeypatch):
    systems = []
    monkeypatch.setattr(annoter_regenerate.llm, "complete_text", lambda system, user, **kwargs: systems.append(system) or "bacaan")
    annoter_regenerate.regenerate("formula", "perbaiki", source_markup="P(a, b)")
    annoter_regenerate.regenerate("formula", "perbaiki", source_markup="x^2 + 1")
    assert formula.COORDINATE_RULES[0] in systems[0]
    assert formula.COORDINATE_RULES[0] not in systems[1]


def test_regenerasi_rumus_bermasalah_mengisi_issues(monkeypatch):
    monkeypatch.setattr(annoter_regenerate.llm, "complete_text", lambda system, user, **kwargs: "a b c")
    result = annoter_regenerate.regenerate("formula", "perbaiki", source_markup=VEC)
    assert any("vektor" in issue for issue in result.issues)


def test_regenerasi_rumus_benar_tanpa_issues(monkeypatch):
    monkeypatch.setattr(annoter_regenerate.llm, "complete_text", lambda system, user, **kwargs: "vektor a")
    assert annoter_regenerate.regenerate("formula", "perbaiki", source_markup=VEC).issues == []


@pytest.fixture
def image(tmp_path):
    path = tmp_path / "g.jpg"
    path.write_bytes(b"x")
    return path


def test_regenerasi_gambar_dibersihkan_dan_notasi_mentah_ditandai(monkeypatch, image):
    monkeypatch.setattr(annoter_regenerate.llm, "complete_vision", lambda *args, **kwargs: 'Grafik "Kecepatan" (m/s) naik, y = x^2.')
    result = annoter_regenerate.regenerate("image", "perbaiki", image_path=image)
    assert result.text == "Grafik Kecepatan (meter per sekon) naik, y = x pangkat dua."
    assert any("notasi mentah" in issue for issue in result.issues)


def test_regenerasi_gambar_bersih_tanpa_issues(monkeypatch, image):
    monkeypatch.setattr(annoter_regenerate.llm, "complete_vision", lambda *args, **kwargs: "Kurva naik dari kiri bawah ke kanan atas.")
    assert annoter_regenerate.regenerate("image", "perbaiki", image_path=image).issues == []
