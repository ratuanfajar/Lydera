import pytest

from common import config, formula


@pytest.mark.parametrize(
    "latex",
    [
        "P(a, b)", "O(0, 0)", "A(x_1, y_1)", "Q(1, 2, 3)", "(h, k)", "(2, 5)", "( 2 ,  5 )",
        chr(92) + "{ (1, 2), (3, 4) " + chr(92) + "}",
        "y = mx " + chr(92) + "pm r", "a " + chr(92) + "mp b", "a ± b", "A'(4, 6)", "M(1,5; 2)", r"A(a + 1, 3)",
        r"A(x_{1}, y_{1})", r"\{ (x, y) \mid y = 2x + 1 \}", r"\left\{ (1, 2), (3, 4) \right\}",
        "x = " + chr(92) + "frac{-b " + chr(92) + "pm " + chr(92) + "sqrt{b^{2} - 4ac}}{2a}",
    ],
)
def test_aturan_koordinat_dipakai_untuk_titik_pasangan_dan_plus_minus(latex):
    assert formula.needs_coordinate_rules(latex)


@pytest.mark.parametrize(
    "latex",
    [
        "f(x) = 2x + 3", "P(A)", "P(A " + chr(92) + "cap B)", "f(x, y)", "x " + chr(92) + "in (-3, 2]", "(x + 1)(x - 1)",
        r"C(5, 2) = 10", r"F(x, y) = x^{2} + y", r"X \sim B(10, 0.5)", r"(-\infty, 3)", r"(3, \infty)", r"\binom{5}{2}",
        "(f " + chr(92) + "circ g)(3)", chr(92) + "{ 1, 2, 3 " + chr(92) + "}", "a " + chr(92) + "pmatrix", "x_{1,2}", "3 + 4",
    ],
)
def test_rumus_lain_tetap_memakai_prompt_dasar(latex):
    assert not formula.needs_coordinate_rules(latex)


@pytest.fixture
def speakers(monkeypatch):
    used = []
    monkeypatch.setattr(formula, "_speak", lambda user, system=None: used.append(system) or "bacaan")
    monkeypatch.setattr(formula.cache, "get", lambda *args: None)
    monkeypatch.setattr(formula.cache, "put", lambda *args: None)
    return used


def test_titik_memakai_prompt_koordinat(speakers):
    formula.convert_checked("P(a, b)")
    assert speakers[0] is formula.COORDINATE_SYSTEM


def test_rumus_biasa_memakai_prompt_dasar(speakers):
    formula.convert_checked("x^2 + 1")
    assert speakers[0] is formula.SYSTEM


def test_kunci_cache_prompt_koordinat_terpisah_dari_prompt_dasar(monkeypatch):
    keys = []
    monkeypatch.setattr(formula.cache, "get", lambda namespace, *key: keys.append(key) or "bacaan")
    formula.convert_checked("P(a, b)")
    formula.convert_checked("x^2 + 1")
    assert keys[0][-1] == config.FORMULA_PROMPT_VERSION + formula.COORDINATE_CACHE_SUFFIX
    assert keys[1][-1] == config.FORMULA_PROMPT_VERSION
