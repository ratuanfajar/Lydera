import json

import pytest

from annoter import annotate, priority
from annoter.preprocess import Block, Route
from annoter.table import TableResult

OK_TABLE = "<table><tr><td>a</td><td>b</td></tr><tr><td>1</td><td>2</td></tr></table>"
EMPTY_TABLE = "<table><tr><td>a</td><td></td></tr><tr><td></td><td></td></tr></table>"
BROKEN_TABLE = "<table><tr><td>a�</td><td>b</td></tr></table>"


@pytest.mark.parametrize(
    "route, html, expected",
    [
        (Route.HEADING, "", "low"),
        (Route.TEXT, "", "low"),
        (Route.FORMULA, "", "normal"),
        (Route.IMAGE, "", "normal"),
        (Route.TABLE, OK_TABLE, "normal"),
        (Route.TABLE, EMPTY_TABLE, "high"),
        (Route.TABLE, BROKEN_TABLE, "high"),
        (Route.TABLE, "<table></table>", "normal"),
    ],
)
def test_review_priority_dasar_per_rute(route, html, expected):
    assert priority.review_priority(Block(route, 0, 0, table_html=html)) == expected


def test_escalate_menaikkan_ke_high_hanya_bila_ditandai():
    block = Block(Route.TEXT, 0, 0)
    assert priority.escalate(block, True) == "high"
    assert priority.escalate(block, False) == "low"


@pytest.mark.parametrize("result, expected", [(TableResult("Baris 1. a: satu."), False), (TableResult("ok", issues=["rusak"]), True), (TableResult("x → y"), True)])
def test_table_flagged_karena_issues_atau_notasi_mentah(result, expected):
    assert priority.table_flagged(result) is expected


def test_batas_sel_kosong_tepat_tiga_puluh_persen_tidak_degraded():
    cells = "<td>x</td>" * 7 + "<td></td>" * 3
    assert not priority.table_degraded(f"<table><tr>{cells}</tr></table>")
    assert priority.table_degraded(f"<table><tr>{cells}<td></td></tr></table>")


def test_annotate_main_menulis_file_dan_kode_keluar_nol(tmp_path, monkeypatch):
    content_list = tmp_path / "doc_content_list.json"
    content_list.write_text(json.dumps([{"type": "text", "text": "Isi paragraf."}]), encoding="utf-8")
    destination = tmp_path / "hasil.json"
    assert annotate.main([str(content_list), str(destination)]) == 0
    assert json.loads(destination.read_text(encoding="utf-8"))[0]["readable_text"] == "Isi paragraf."


def test_annotate_main_kode_keluar_satu_bila_ada_blok_gagal(tmp_path, monkeypatch):
    content_list = tmp_path / "doc_content_list.json"
    content_list.write_text(json.dumps([{"type": "equation", "text": "$$x$$"}]), encoding="utf-8")

    def convert(latex):
        raise ValueError("rusak")

    monkeypatch.setattr(annotate.formula, "convert_checked", convert)
    destination = tmp_path / "hasil.json"
    assert annotate.main([str(content_list), str(destination)]) == 1
    assert json.loads(destination.read_text(encoding="utf-8"))[0]["review_priority"] == "high"
