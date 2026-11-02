import json

import pytest

from annoter.preprocess import Route, preprocess


def load(tmp_path, items):
    path = tmp_path / "doc_content_list.json"
    path.write_text(json.dumps(items), encoding="utf-8")
    return preprocess(path)


def test_text_dengan_level_menjadi_heading(tmp_path):
    block = load(tmp_path, [{"type": "text", "text": "Bab 1", "text_level": 1, "page_idx": 2}])[0]
    assert (block.route, block.level, block.page, block.text) == (Route.HEADING, 1, 2, "Bab 1")


def test_text_tanpa_level_menjadi_text(tmp_path):
    block = load(tmp_path, [{"type": "text", "text": "Isi paragraf."}])[0]
    assert (block.route, block.level) == (Route.TEXT, None)


def test_equation_menjadi_formula_dan_pembatas_dibuang(tmp_path):
    block = load(tmp_path, [{"type": "equation", "text": "$$ x^{2} + 1 $$"}])[0]
    assert (block.route, block.latex) == (Route.FORMULA, "x^{2} + 1")


def test_table_menjadi_table_dengan_html_dan_caption(tmp_path):
    block = load(tmp_path, [{"type": "table", "table_body": "<table></table>", "table_caption": ["Tabel", "1.1"], "img_path": "images/t.jpg"}])[0]
    assert (block.route, block.table_html, block.caption) == (Route.TABLE, "<table></table>", "Tabel 1.1")
    assert block.image_path.name == "t.jpg"


@pytest.mark.parametrize("kind, caption_key", [("image", "image_caption"), ("chart", "chart_caption")])
def test_image_dan_chart_menjadi_image(tmp_path, kind, caption_key):
    block = load(tmp_path, [{"type": kind, "img_path": "images/g.jpg", caption_key: ["Gambar 1"]}])[0]
    assert (block.route, block.caption) == (Route.IMAGE, "Gambar 1")


@pytest.mark.parametrize("kind", ["header", "footer", "page_number"])
def test_noise_dibuang(tmp_path, kind):
    assert load(tmp_path, [{"type": kind, "text": "12"}]) == []


def test_math_inline_dalam_teks_dipecah_menjadi_segmen(tmp_path):
    block = load(tmp_path, [{"type": "text", "text": "Nilai $x^2$ adalah dua."}])[0]
    assert [(s.is_formula, s.content) for s in block.segments] == [(False, "Nilai "), (True, "x^2"), (False, " adalah dua.")]


def test_teks_kosong_dibuang(tmp_path):
    assert load(tmp_path, [{"type": "text", "text": "   "}]) == []


def test_tipe_tidak_dikenal_dibuang_dan_urutan_blok_berlanjut(tmp_path):
    blocks = load(tmp_path, [{"type": "text", "text": "a"}, {"type": "aneh"}, {"type": "text", "text": "b"}])
    assert [(b.order, b.text) for b in blocks] == [(0, "a"), (1, "b")]


def test_text_level_nol_tetap_text_biasa(tmp_path):
    assert load(tmp_path, [{"type": "text", "text": "Isi.", "text_level": 0}])[0].route == Route.TEXT
