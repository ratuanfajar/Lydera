import json
from types import SimpleNamespace

import pytest

from clarifier import agent, table

SPEC = {"judul": "Sifat sudut", "kolom": ["jenis", "besar"], "baris": [["pusat", "80"], ["keliling", "40"]]}


def test_tanpa_tabel_mengembalikan_none():
    assert table.build(None, ["teks"]) is None
    assert table.build({}, ["teks"]) is None


def test_tabel_valid_dengan_angka_dari_sumber_diberi_bacaan_dan_ringkasan():
    result = table.build(SPEC, ["Sudut pusat 80 derajat dan sudut keliling 40 derajat."])
    assert result["issues"] == [] and result["tabel"]["kolom"] == ["jenis", "besar"]
    assert "Ada 2 kolom" in result["tabel_bacaan"] and "Baris 1" in result["tabel_bacaan"] and result["tabel_ringkasan"]


def test_angka_yang_dihitung_di_ringkasan_dianggap_berdasar():
    assert table.build(SPEC, ["80 dan 40"])["issues"] == []
    assert table.build(SPEC, ["sumber tanpa angka", "ringkasan menyebut 80 dan 40"])["issues"] == []


def test_angka_yang_tidak_ada_di_sumber_membuang_tabel():
    result = table.build(SPEC, ["hanya 80"])
    assert result["tabel"] is None and "40" in result["issues"][0]


@pytest.mark.parametrize("spec", [
    {"judul": "t", "kolom": ["a", "b"], "baris": [["x"]]},
    {"judul": "", "kolom": ["a"], "baris": [["x"]]},
    {"judul": "t", "kolom": ["a"], "baris": [["**tebal**"]]},
    {"judul": "t"},
    "bukan objek",
])
def test_struktur_atau_isi_tidak_valid_membuang_tabel(spec):
    result = table.build(spec, ["x"])
    assert result["tabel"] is None and result["issues"]


def compose(args):
    return SimpleNamespace(function=SimpleNamespace(arguments=json.dumps(args, ensure_ascii=False)))


def test_finalize_menyertakan_tabel_dan_bacaan_pada_hasil_agen():
    args = {
        "sources": [{"source_type": "modul", "label": "Bab lingkaran", "reference": "7", "evidence": "Sudut pusat 80 derajat.", "justification": "Relevan."}],
        "summary": "Sudut pusat dua kali sudut keliling.", "tabel": SPEC,
    }
    result = agent._finalize(compose(args), {"7": "Sudut pusat 80 derajat dan sudut keliling 40 derajat."}, [], {"klass": "inti"})
    assert result["tabel"]["judul"] == "Sifat sudut" and "Baris 1" in result["tabel_bacaan"] and result["message"]


def test_finalize_tabel_bermasalah_dibuang_tanpa_menggagalkan_jawaban():
    args = {
        "sources": [{"source_type": "modul", "label": "Bab lingkaran", "reference": "7", "evidence": "Sudut pusat 80 derajat.", "justification": "Relevan."}],
        "summary": "Sudut pusat dua kali sudut keliling.", "tabel": {"judul": "t", "kolom": ["a"], "baris": [["999"]]},
    }
    result = agent._finalize(compose(args), {"7": "Sudut pusat 80 derajat."}, [], {"klass": "inti"})
    assert result["tabel"] is None and result["message"] and any("999" in issue for issue in result["format_issues"])


def test_run_selalu_menyertakan_kunci_tabel(monkeypatch):
    monkeypatch.setattr(agent, "_run", lambda *args: {"status": "out_of_scope", "message": "x"})
    result = agent.run("q", [], None)
    assert result["tabel"] is None and result["tabel_bacaan"] is None and result["rumus"] == []
