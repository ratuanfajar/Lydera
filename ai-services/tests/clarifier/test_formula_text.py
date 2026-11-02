import pytest

from clarifier import formula_text

NORMALIZE_CASES = [
    (r"\beta _ { 1 } = 2 \alpha _ { 1 }", "beta_1=2alpha_1"),
    (r"H \left( t \right) = 2 0 . 0 0 0 . 0 0 0 \times e ^ { - 0 . 2 5 t } ,", "h(t)=20.000.000*e^(-0.25t),"),
    (r"\frac { a + b } { c }", "(a+b)/(c)"),
    (r"\dfrac{1}{\frac{a}{b}}", "(1)/((a)/(b))"),
    (r"\frac{1}{\frac{a}{b}}", "(1)/((a)/(b))"),
    (r"\sqrt { x ^ { 2 } + 1 }", "sqrt(x^2+1)"),
    (r"x ^ { 2 } - 5 x + 6 = 0", "x^2-5x+6=0"),
    ("x^2 - 5x + 6 = 0", "x^2-5x+6=0"),
    ("x² − 5x + 6 = 0", "x^2-5x+6=0"),
    ("a**2 + b**2 = c**2", "a^2+b^2=c^2"),
    (r"a \leq b \neq c \pm d", "a<=b!=c+-d"),
    (r"f \circ g", "fog"),
    (r"\mathrm { d a n }", "dan"),
    (r"\begin{array} { c } { \beta = \beta _ { 1 } + \beta _ { 2 } } \\ { x } \end{array}", "beta=beta_1+beta_2;x"),
    ("", ""),
    ("x^10", "x^(10)"),
    (r"x^{10}", "x^(10)"),
    ("f^-1(x)", "f^(-1)(x)"),
    (r"f^{-1}(x)", "f^(-1)(x)"),
    ("x^2y", "x^2y"),
    ("f(x) = 1/x", "f(x)=(1)/(x)"),
    (r"f(x) = \frac{1}{x}", "f(x)=(1)/(x)"),
    ("x/2", "(x)/(2)"),
    (r"\frac{x}{2}", "(x)/(2)"),
    ("1/(x+1)", "(1)/(x+1)"),
    (r"\frac{1}{x+1}", "(1)/(x+1)"),
    ("(a+b)/c", "(a+b)/(c)"),
    (r"\frac{a+b}{c}", "(a+b)/(c)"),
    ("(x^2 - 1)/x", "(x^2-1)/(x)"),
    ("f(x)/g(x)", "f(x)/g(x)"),
    ("2x/3", "(2x)/(3)"),
    ("(x+4)/(2x-5)", "(x+4)/(2x-5)"),
    (r"\frac{x+4}{2x-5}", "(x+4)/(2x-5)"),
]

SPAN_CASES = [
    ("Bagaimana mencari akar dari x^2 - 5x + 6 = 0 ?", ["x^2-5x+6=0"]),
    ("nilai x jika 2x+3=11", ["2x+3=11"]),
    ("Apa itu a^2 + b^2 = c^2?", ["a^2+b^2=c^2"]),
    ("jelaskan fungsi komposisi", []),
    ("sudut 30 derajat dan 45 derajat", []),
    ("berapa x - 2 jika x = 5", []),
    ("tentukan x = 2", []),
    ("(f o g)(x) = f(g(x))", ["(fog)(x)=f(g(x))"]),
    ("tidak-berhingga dan bilangan 1.000.000", []),
    ("hitung 3x + 4 = 19 dan 2x - 1 = 7", ["3x+4=19", "2x-1=7"]),
    ("x^2-5x+6=0.", ["x^2-5x+6=0"]),
    ("domain dari f(x) = sqrt(x-3) + 4", ["f(x)=sqrt(x-3)+4"]),
    ("Hitung (f o g)(x) jika f(x) = 1/x dan g(x) = 2x+1", ["f(x)=(1)/(x)", "g(x)=2x+1"]),
    ("Apakah g o f = f o g jika f(x) = 2x + 1 dan g(x) = x^2 + 4?", ["gof=fog", "f(x)=2x+1", "g(x)=x^2+4"]),
    ("AB + PC = AC + PB", ["ab+pc=ac+pb"]),
    ("h(t) = 20.000.000 * e^(-0.25t)", ["h(t)=20.000.000*e^(-0.25t)"]),
]


@pytest.mark.parametrize(("raw", "expected"), NORMALIZE_CASES)
def test_normalize_formula_menyamakan_notasi(raw, expected):
    assert formula_text.normalize_formula(raw) == expected


def test_normalize_formula_membedakan_rumus_berbeda():
    assert formula_text.normalize_formula("x^2-5x+6=0") != formula_text.normalize_formula("x^2+5x+6=0")


@pytest.mark.parametrize(("question", "expected"), SPAN_CASES)
def test_formula_spans_mengambil_rumus_dari_pertanyaan(question, expected):
    assert formula_text.formula_spans(question) == expected
