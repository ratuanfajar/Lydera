import pytest

from common.jsonutil import parse_json


@pytest.mark.parametrize(
    "raw, want",
    [
        (r'{"a": "$\\frac{1}{2}$"}', r"$\frac{1}{2}$"),
        (r'{"a": "$\frac{1}{2}$"}', r"$\frac{1}{2}$"),
        (r'{"a": "$a \times b$"}', r"$a \times b$"),
        (r'{"a": "$a \\times b$"}', r"$a \times b$"),
        (r'{"a": "$a \neq b$"}', r"$a \neq b$"),
        (r'{"a": "$x \leq 5$"}', r"$x \leq 5$"),
        (r'{"a": "$a \nexists b$"}', r"$a \nexists b$"),
        (r'{"a": "baris1\nbaris2"}', "baris1\nbaris2"),
        (r'{"a": "\% sisa"}', r"\% sisa"),
        (r'{"a": "dia berkata \"hai\""}', 'dia berkata "hai"'),
        (r'{"a": "Δ"}', "Δ"),
    ],
)
def test_parse_json_latex_menjaga_perintah_latex(raw, want):
    assert parse_json(raw, latex=True)["a"] == want


def test_parse_json_tanpa_latex_menggandakan_escape_tak_sah():
    assert parse_json(r'{"a": "\% sisa"}')["a"] == r"\% sisa"


@pytest.mark.parametrize(
    "raw, want",
    [
        (r'{"a": "x\tNama"}', r"x\tNama"),
        (r'{"a": "baris\notomatis"}', r"baris\notomatis"),
    ],
)
def test_parse_json_tanpa_latex_menggandakan_backslash_escape_sah(raw, want):
    assert parse_json(raw)["a"] == want


def test_parse_json_membuang_pagar_kode_json():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
