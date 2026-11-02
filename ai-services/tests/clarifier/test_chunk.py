import json
from pathlib import Path

import pytest

from clarifier import chunk

BAB1 = Path(__file__).resolve().parents[2] / "clarifier" / "eval" / "blocks" / "bab1.json"


def block(id, kind, text, markup=""):
    return {"id": id, "block_type": kind, "readable_text": text, "reading_order": id, "source_markup": markup}


@pytest.fixture
def chunks():
    blocks = [
        block(1, "text", "Teks sebelum heading."),
        block(2, "heading", "Kementerian Pendidikan 2021 ISBN: 978-602"),
        block(3, "text", "Penulis: Dicky."),
        block(4, "heading", "Akar persamaan kuadrat"),
        block(5, "text", "Persamaan kuadrat berbentuk a x kuadrat tambah b x tambah c.", "Persamaan $a x ^ { 2 } + b x + c = 0$ memiliki akar."),
        block(6, "formula", "x kuadrat dikurangi lima x tambah enam sama dengan nol", "x ^ { 2 } - 5 x + 6 = 0"),
        block(7, "formula", "x kuadrat tambah lima x tambah enam sama dengan nol", "x ^ { 2 } + 5 x + 6 = 0"),
        block(8, "heading", "Kosong"),
        block(9, "heading", "Panjang"),
        block(10, "text", "a" * 900),
        block(11, "text", "b" * 900),
        block(12, "text", "c" * 2000),
        block(13, "text", "d" * 100),
    ]
    return chunk.build_chunks(7, blocks)


def test_build_chunks_membuang_heading_metadata_dan_memberi_pembuka(chunks):
    headings = [c.heading for c in chunks]
    assert headings == ["Pembuka", "Akar persamaan kuadrat", "Kosong", "Panjang", "Panjang", "Panjang", "Panjang"]


def test_build_chunks_pembuka_berisi_teks_sebelum_heading(chunks):
    pembuka = chunks[0]
    assert pembuka.block_ids == [1]
    assert pembuka.formula_norm == ""
    assert pembuka.text == "Pembuka: Teks sebelum heading."


def test_build_chunks_mengumpulkan_blok_dan_rumus_ternormalisasi(chunks):
    akar = chunks[1]
    assert akar.block_ids == [4, 5, 6, 7]
    assert akar.formula_norm == "ax^2+bx+c=0;x^2-5x+6=0;x^2+5x+6=0"
    assert akar.text.startswith("Akar persamaan kuadrat: Persamaan kuadrat berbentuk")
    assert (akar.reading_order_start, akar.reading_order_end) == (4, 7)


def test_build_chunks_heading_tanpa_isi_tetap_jadi_chunk(chunks):
    kosong = chunks[2]
    assert kosong.block_ids == [8]
    assert kosong.text == "Kosong"
    assert kosong.formula_norm == ""


def test_build_chunks_memecah_bagian_panjang(chunks):
    panjang = chunks[3:]
    assert [c.block_ids for c in panjang] == [[9, 10], [11], [12], [13]]
    assert [c.reading_order_start for c in panjang[:2]] == [9, 11]
    assert all(c.text.startswith("Panjang: ") for c in panjang)


def test_build_chunks_membuang_pembuka_berisi_isbn():
    blocks = [block(1, "text", "Hak cipta. ISBN: 978-602-244-789-5"), block(2, "heading", "Bab 1"), block(3, "text", "Isi bab.")]
    assert [c.heading for c in chunk.build_chunks(7, blocks)] == ["Bab 1"]


def test_build_chunks_mempertahankan_heading_yang_memuat_kata_hak_cipta():
    blocks = [block(1, "heading", "Hak Cipta dan Paten"), block(2, "text", "Materi tentang hak cipta.")]
    assert [c.heading for c in chunk.build_chunks(7, blocks)] == ["Hak Cipta dan Paten"]


def test_build_chunks_daftar_kosong_menghasilkan_daftar_kosong():
    assert chunk.build_chunks(1, []) == []


def test_build_chunks_menerima_blok_tanpa_source_markup():
    legacy = [
        {"id": 1, "block_type": "heading", "readable_text": "H", "reading_order": 1},
        {"id": 2, "block_type": "text", "readable_text": "t", "reading_order": 2},
    ]
    built = chunk.build_chunks(1, legacy)
    assert built[0].text == "H: t"
    assert built[0].formula_norm == ""


@pytest.fixture
def bab1_chunks():
    rows = json.loads(BAB1.read_text(encoding="utf-8"))
    for row in rows:
        row["id"], row["reading_order"] = int(row["id"]), int(row["reading_order"])
    return chunk.build_chunks(1, rows)


def test_build_chunks_bab1_tidak_menghasilkan_chunk_multi_blok_melebihi_batas(bab1_chunks):
    oversize = [c for c in bab1_chunks if len(c.text) > chunk.MAX_CHUNK_CHARS + 200 and len(c.block_ids) > 2]
    assert oversize == []


def test_build_chunks_bab1_tidak_menduplikasi_blok_dalam_chunk(bab1_chunks):
    assert all(len(set(c.block_ids)) == len(c.block_ids) for c in bab1_chunks)
