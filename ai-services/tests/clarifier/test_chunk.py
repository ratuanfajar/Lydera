import json
from pathlib import Path

import pytest

from clarifier import chunk

BAB1 = Path(__file__).resolve().parents[2] / "clarifier" / "eval" / "blocks" / "bab1.json"


def block(id, kind, text, markup=""):
    return {"id": id, "block_type": kind, "readable_text": text, "reading_order": id, "source_markup": markup}


def heading(id, text):
    return block(id, "heading", text)


def prose(id, size):
    return block(id, "text", chr(96 + id % 26) * size)


def test_daftar_kosong_menghasilkan_daftar_kosong():
    assert chunk.build_chunks(1, []) == []


def test_teks_sebelum_heading_menjadi_pembuka():
    built = chunk.build_chunks(7, [block(1, "text", "Teks sebelum heading."), heading(2, "Bab")])
    assert built[0].heading == "Pembuka" and built[0].block_ids == [1, 2]
    assert built[0].text == "Pembuka: Teks sebelum heading. Bab"


def test_section_metadata_penerbit_dibuang():
    blocks = [block(1, "text", "Hak cipta. ISBN: 978-602-244-789-5"), heading(2, "Bab 1"), block(3, "text", "Isi bab."),
              heading(4, "Kementerian ISBN: 978"), block(5, "text", "Penulis."), heading(6, "Bab 2"), block(7, "text", "Isi dua.")]
    built = chunk.build_chunks(7, blocks)
    assert [i for c in built for i in c.block_ids] == [2, 3, 6, 7]


def test_heading_yang_memuat_kata_hak_cipta_dipertahankan():
    built = chunk.build_chunks(7, [heading(1, "Hak Cipta dan Paten"), block(2, "text", "Materi tentang hak cipta.")])
    assert [c.heading for c in built] == ["Hak Cipta dan Paten"]


def test_section_pendek_berurutan_digabung_dalam_satu_chunk():
    blocks = [heading(1, "A"), block(2, "text", "satu"), heading(3, "B"), block(4, "text", "dua"), heading(5, "C"), block(6, "text", "tiga")]
    built = chunk.build_chunks(1, blocks)
    assert len(built) == 1
    assert built[0].heading == "A" and built[0].block_ids == [1, 2, 3, 4, 5, 6]
    assert built[0].text == "A: satu B: dua C: tiga"


def test_dipotong_di_heading_setelah_mencapai_target():
    blocks = [heading(1, "A"), prose(2, chunk.TARGET_CHUNK_CHARS), heading(3, "B"), prose(4, chunk.TARGET_CHUNK_CHARS)]
    built = chunk.build_chunks(1, blocks)
    assert [c.heading for c in built] == ["A", "B"]
    assert built[0].block_ids == [1, 2] and built[1].block_ids[-2:] == [3, 4]


def test_section_panjang_dipotong_di_batas_block_sebelum_batas_maksimum():
    half = chunk.MAX_CHUNK_CHARS // 2 + 10
    blocks = [heading(1, "A"), prose(2, half), prose(3, half), prose(4, half)]
    built = chunk.build_chunks(1, blocks)
    assert [c.block_ids[-1] for c in built] == [2, 3, 4]
    assert all(len(c.text) <= chunk.MAX_CHUNK_CHARS + chunk.OVERLAP_MAX_CHARS + 50 for c in built)
    assert all(c.heading == "A" and c.text.startswith("A: ") or c.text.startswith("A:") for c in built)


def test_heading_tidak_ditinggal_sendirian_di_ujung_chunk():
    blocks = [heading(1, "A"), prose(2, chunk.MAX_CHUNK_CHARS - 20), heading(3, "B"), prose(4, 200)]
    built = chunk.build_chunks(1, blocks)
    assert built[0].block_ids == [1, 2]
    assert built[1].block_ids[-2:] == [3, 4]


def test_block_tunggal_melebihi_batas_tetap_utuh():
    built = chunk.build_chunks(1, [heading(1, "A"), prose(2, chunk.MAX_CHUNK_CHARS * 2)])
    assert [c.block_ids for c in built] == [[1, 2]]


def test_overlap_satu_block_terakhir_bila_cukup_pendek():
    blocks = [heading(1, "A"), prose(2, 700), block(3, "text", "p" * 100), prose(4, 700)]
    built = chunk.build_chunks(1, blocks)
    assert built[0].block_ids == [1, 2, 3]
    assert built[1].block_ids == [3, 4] and built[1].text.startswith("A: ppp")


def test_tanpa_overlap_bila_block_terakhir_panjang_atau_chunk_hanya_satu_block():
    half = chunk.MAX_CHUNK_CHARS // 2 + 10
    built = chunk.build_chunks(1, [heading(1, "A"), prose(2, half), prose(3, half), prose(4, half)])
    assert built[1].block_ids == [3]
    assert built[2].block_ids == [4]


def test_block_pertama_tiap_chunk_unik_untuk_rujukan_sitasi():
    blocks = [heading(1, "A")] + [prose(i, 500) for i in range(2, 30)]
    built = chunk.build_chunks(1, blocks)
    firsts = [c.block_ids[0] for c in built]
    assert len(built) > 3 and len(set(firsts)) == len(firsts)


def test_chunk_terakhir_pendek_digabung_bila_muat():
    blocks = [heading(1, "A"), prose(2, chunk.TARGET_CHUNK_CHARS), heading(3, "B"), block(4, "text", "singkat")]
    built = chunk.build_chunks(1, blocks)
    assert len(built) == 1 and built[0].block_ids == [1, 2, 3, 4]


def test_rumus_ternormalisasi_dan_urutan_baca():
    blocks = [
        heading(1, "Akar persamaan kuadrat"),
        block(2, "text", "Persamaan kuadrat berbentuk a x kuadrat tambah b x tambah c.", "Persamaan $a x ^ { 2 } + b x + c = 0$ memiliki akar."),
        block(3, "formula", "x kuadrat dikurangi lima x tambah enam sama dengan nol", "x ^ { 2 } - 5 x + 6 = 0"),
        block(4, "formula", "x kuadrat tambah lima x tambah enam sama dengan nol", "x ^ { 2 } + 5 x + 6 = 0"),
    ]
    built = chunk.build_chunks(7, blocks)[0]
    assert built.formula_norm == "ax^2+bx+c=0;x^2-5x+6=0;x^2+5x+6=0"
    assert built.text.startswith("Akar persamaan kuadrat: Persamaan kuadrat berbentuk")
    assert (built.reading_order_start, built.reading_order_end) == (1, 4)


def test_menerima_block_tanpa_source_markup():
    legacy = [
        {"id": 1, "block_type": "heading", "readable_text": "H", "reading_order": 1},
        {"id": 2, "block_type": "text", "readable_text": "t", "reading_order": 2},
    ]
    built = chunk.build_chunks(1, legacy)
    assert built[0].text == "H: t" and built[0].formula_norm == ""


@pytest.fixture
def bab1_chunks():
    rows = json.loads(BAB1.read_text(encoding="utf-8"))
    for row in rows:
        row["id"], row["reading_order"] = int(row["id"]), int(row["reading_order"])
    return chunk.build_chunks(1, rows)


def test_bab1_tidak_menghasilkan_chunk_pendek_atau_melebihi_batas(bab1_chunks):
    assert all(len(c.text) >= chunk.MIN_TAIL_CHARS for c in bab1_chunks)
    assert all(len(c.text) <= chunk.MAX_CHUNK_CHARS + chunk.OVERLAP_MAX_CHARS + 100 or len(c.block_ids) <= 2 for c in bab1_chunks)


def test_bab1_block_tidak_duplikat_dalam_chunk_dan_rujukan_unik(bab1_chunks):
    assert all(len(set(c.block_ids)) == len(c.block_ids) for c in bab1_chunks)
    firsts = [c.block_ids[0] for c in bab1_chunks]
    assert len(set(firsts)) == len(firsts)
