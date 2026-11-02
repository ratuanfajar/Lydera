
import pytest

from annoter import annotate
from annoter.preprocess import Block, Route, Segment
from annoter.table import TableResult
from common import llm


def text_block(order, text="Paragraf biasa."):
    return Block(Route.TEXT, order, 0, text=text, segments=[Segment(False, text)])


def image_block(order):
    return Block(Route.IMAGE, order, 0, caption="Gambar 1")


def table_block(order):
    return Block(Route.TABLE, order, 0, table_html="<table></table>", caption="Tabel 1")


def formula_block(order, latex="x^2"):
    return Block(Route.FORMULA, order, 0, latex=latex)


@pytest.fixture
def window(monkeypatch):
    def use(blocks):
        monkeypatch.setattr(annotate, "preprocess", lambda path: blocks)
        return annotate.annotate_window("x_content_list.json")

    monkeypatch.setattr(annotate.config, "LLM_MAX_WORKERS", 2)
    monkeypatch.setattr(annotate.formula, "convert_checked", lambda latex: ("bacaan " + latex, []))
    monkeypatch.setattr(annotate.table, "linearize_table", lambda block: TableResult("tabel biasa"))
    monkeypatch.setattr(annotate.image, "annotate_image", lambda block, context: annotate.image.ImageAnnotation("geometri", "gambar biasa"))
    return use


def test_gambar_gagal_filter_konten_tidak_membunuh_blok_lain(window, monkeypatch):
    def annotate_image(block, context):
        raise llm.ContentFilterError("ditolak")

    monkeypatch.setattr(annotate.image, "annotate_image", annotate_image)
    result = window([text_block(0), image_block(1), formula_block(2)])
    assert [b.block_type for b in result.blocks] == ["text", "image", "formula"]
    assert result.blocks[0].readable_text == "Paragraf biasa."
    assert result.blocks[2].readable_text == "bacaan x^2"
    assert (result.blocks[1].readable_text, result.blocks[1].review_priority, result.blocks[1].caption) == ("", "high", "Gambar 1")
    assert (result.failed, result.attempted) == (1, 2)


def test_tabel_gagal_value_error_blok_lain_selesai(window, monkeypatch):
    def linearize(block):
        raise ValueError("JSON rusak")

    monkeypatch.setattr(annotate.table, "linearize_table", linearize)
    result = window([table_block(0), image_block(1)])
    assert (result.blocks[0].readable_text, result.blocks[0].review_priority, result.blocks[0].source_markup) == ("", "high", "<table></table>")
    assert result.blocks[1].readable_text == "gambar biasa"
    assert result.failed == 1


def test_rumus_gagal_blok_lain_selesai(window, monkeypatch):
    def convert(latex):
        if latex == "bad":
            raise TimeoutError("lambat")
        return ("bacaan " + latex, [])

    monkeypatch.setattr(annotate.formula, "convert_checked", convert)
    result = window([formula_block(0, "bad"), formula_block(1, "ok")])
    assert (result.blocks[0].readable_text, result.blocks[0].review_priority, result.blocks[0].source_markup) == ("", "high", "bad")
    assert result.blocks[1].readable_text == "bacaan ok"


def test_teks_dengan_rumus_inline_gagal_tetap_menyimpan_teks(window, monkeypatch):
    monkeypatch.setattr(annotate.formula, "convert_checked", lambda latex: (_ for _ in ()).throw(ValueError("gagal")))
    block = Block(Route.TEXT, 0, 0, text="Nilai $x$ adalah dua.", segments=[Segment(False, "Nilai "), Segment(True, "x"), Segment(False, " adalah dua.")])
    result = window([block])
    assert result.blocks[0].readable_text == "Nilai rumus tidak terbaca adalah dua."
    assert result.blocks[0].review_priority == "high"
    assert (result.failed, result.attempted) == (1, 1)


def test_rumus_inline_gagal_hanya_rumus_itu_yang_diganti(window, monkeypatch):
    def convert(latex):
        if latex == "bad":
            raise ValueError("gagal")
        return ("bacaan " + latex, [])

    monkeypatch.setattr(annotate.formula, "convert_checked", convert)
    segments = [Segment(False, "A "), Segment(True, "ok"), Segment(False, " lalu "), Segment(True, "bad"), Segment(False, ".")]
    result = window([Block(Route.TEXT, 0, 0, text="A $ok$ lalu $bad$.", segments=segments)])
    assert result.blocks[0].readable_text == "A bacaan ok lalu rumus tidak terbaca."
    assert (result.blocks[0].review_priority, result.failed) == ("high", 1)


def test_error_pada_blok_tanpa_llm_tidak_ditelan(window, monkeypatch):
    monkeypatch.setattr(annotate, "strip_tags", lambda text: (_ for _ in ()).throw(TypeError("bug kode")))
    with pytest.raises(TypeError):
        window([Block(Route.HEADING, 0, 0, text="Judul", level=1, segments=[Segment(False, "Judul")])])


def test_teks_tanpa_rumus_tidak_dihitung_sebagai_panggilan_llm(window):
    result = window([text_block(0), text_block(1)])
    assert (result.failed, result.attempted) == (0, 0)
