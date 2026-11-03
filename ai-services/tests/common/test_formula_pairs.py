import pytest

from common import formula
from common.formula_check import spoken_issues


@pytest.mark.parametrize(
    "latex, expected",
    [("(-2,5)", "(-2, 5)"), ("(1,6)", "(1, 6)"), ("( 3 , -4 )", "(3, -4)"), ("(2.5,7)", "(2.5, 7)"), ("A(1,2)", "A(1, 2)"), ("(a,b)", "(a,b)"), ("f(x)", "f(x)")],
)
def test_pasangan_bilangan_diberi_spasi_setelah_koma(latex, expected):
    assert formula.spaced_pairs(latex) == expected


def test_convert_checked_memakai_rumus_yang_sudah_dinormalisasi(monkeypatch):
    seen = []
    monkeypatch.setattr(formula.cache, "get", lambda *args: None)
    monkeypatch.setattr(formula.cache, "put", lambda *args: None)
    monkeypatch.setattr(formula, "_speak", lambda user, system=None: seen.append(user) or "titik dengan koordinat negatif dua dan lima")
    formula.convert_checked("$(-2,5)$".strip("$"))
    assert seen and "(-2, 5)" in seen[0] and "(-2,5)" not in seen[0]


@pytest.mark.parametrize("spoken", ["titik dengan koordinat negatif satu dan lima dan intolerablemente mislike?", "satu per dua!"])
def test_bacaan_dengan_tanda_tanya_atau_seru_ditandai(spoken):
    assert any("tanda tanya" in issue for issue in spoken_issues("(-1, 5)", spoken))


def test_bacaan_normal_tidak_ditandai():
    assert not any("tanda tanya" in issue for issue in spoken_issues("(-1, 5)", "titik dengan koordinat negatif satu dan lima"))


def test_tanya_telanjang_dibakukan_menjadi_tanda_tanya():
    from common.formula import standard_marks

    assert standard_marks("a titik g komposisi f sama dengan f komposisi g tanya") == "a titik g komposisi f sama dengan f komposisi g tanda tanya"
    assert standard_marks("g komposisi h tanda tanya") == "g komposisi h tanda tanya"


def test_rumus_sumber_dengan_subskrip_kosong_ditandai_rusak_ocr():
    from common.formula_check import source_issues

    assert source_issues("g _ { } \circ { f , f } !")
    assert source_issues("x^{ }")
    assert source_issues("x _ { 1 } + y ^ { 2 }") == []
