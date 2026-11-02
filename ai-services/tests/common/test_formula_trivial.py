import pytest

from common import formula


@pytest.fixture
def speaker(monkeypatch):
    calls = []
    monkeypatch.setattr(formula, "_speak", lambda user, system=None: calls.append(user) or "bacaan")
    return calls


@pytest.mark.parametrize(
    "latex, reading",
    [("x", "x"), ("R", "R"), ("7", "tujuh"), ("0", "nol"), (chr(92) + "alpha", "alfa"), (chr(92) + "theta", "teta"), (chr(92) + "Delta", "delta")],
)
def test_ekspresi_tunggal_dibaca_tanpa_llm(speaker, latex, reading):
    assert formula.convert_checked(latex) == (reading, [])
    assert speaker == []


@pytest.mark.parametrize("latex", ["12", "x^2", "ab", chr(92) + "frac{1}{2}", "x_1"])
def test_ekspresi_lain_tetap_lewat_llm(monkeypatch, speaker, latex):
    monkeypatch.setattr(formula.cache, "get", lambda *args: None)
    monkeypatch.setattr(formula.cache, "put", lambda *args: None)
    formula.convert_checked(latex)
    assert speaker


def test_ekspresi_kosong_menghasilkan_bacaan_kosong(speaker):
    assert formula.convert_checked("  ") == ("", [])


def test_prompt_koordinat_memuat_aturan_titik_dan_plus_minus():
    system = formula.formula_system(coordinate=True)
    assert "titik P dengan koordinat a dan b" in system
    assert "plus atau minus" in system


def test_prompt_dasar_tidak_berubah_oleh_aturan_koordinat():
    system = formula.formula_system()
    assert "koordinat" not in system
    assert "plus atau minus" not in system
    assert system == formula.SYSTEM
