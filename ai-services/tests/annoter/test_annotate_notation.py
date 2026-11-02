import pytest

from annoter import annotate, priority
from annoter.image import ImageAnnotation
from annoter.preprocess import Block, Route
from annoter.table import TableResult


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Kurva naik dari kiri bawah ke kanan atas.", "normal"),
        ("Grafik fungsi x^2 membuka ke atas.", "high"),
        ("Panah A → B menunjukkan urutan.", "high"),
        ("Sudut ∠ABC besarnya sembilan puluh derajat.", "high"),
    ],
)
def test_gambar_bernotasi_mentah_berprioritas_tinggi(text, expected):
    assert priority.image_priority(ImageAnnotation("geometri", text)) == expected


@pytest.mark.parametrize("text, expected", [("Kolom a, kolom b. Baris 1. a: satu; b: dua.", "normal"), ("Baris 1. a: x → y.", "high")])
def test_tabel_bernotasi_mentah_berprioritas_tinggi(monkeypatch, text, expected):
    monkeypatch.setattr(annotate.table, "linearize_table", lambda block: TableResult(text))
    block = Block(Route.TABLE, 0, 0, table_html="<table><tr><td>1</td></tr></table>")
    assert annotate.annotate_block(block, [block], 0).review_priority == expected
