import json

import pytest

from annoter import annoter_pipeline
from annoter.annotate import Annotated, WindowResult


def test_satu_window_gagal_dari_empat_tetap_menghasilkan_yang_lain(window_names, make_windows, patch_annotate, window_result):
    root = make_windows(window_names)
    patch_annotate({**dict.fromkeys(window_names, window_result()), "p0003-0005": ValueError("rusak")})
    files = annoter_pipeline.run(root)
    assert [f.parent.name for f in files] == ["p0000-0002", "p0006-0008", "p0009-0011"]
    assert all(json.loads(f.read_text(encoding="utf-8"))[0]["readable_text"] == "isi" for f in files)
    assert not (root / "p0003-0005" / "annotated.json").exists()


def test_terlalu_banyak_window_gagal_melempar_error_dan_file_sukses_tetap_ada(window_names, make_windows, patch_annotate, window_result):
    root = make_windows(window_names[:2])
    patch_annotate({"p0000-0002": window_result(), "p0003-0005": RuntimeError("rusak")})
    with pytest.raises(annoter_pipeline.AnnotationFailure, match="p0003-0005"):
        annoter_pipeline.run(root)
    assert (root / "p0000-0002" / "annotated.json").exists()


def test_semua_window_gagal_melempar_error(window_names, make_windows, patch_annotate):
    root = make_windows(window_names[:2])
    patch_annotate(dict.fromkeys(window_names[:2], RuntimeError("rusak")))
    with pytest.raises(annoter_pipeline.AnnotationFailure):
        annoter_pipeline.run(root)


def test_satu_window_tunggal_gagal_melempar_error(window_names, make_windows, patch_annotate):
    root = make_windows(window_names[:1])
    patch_annotate({"p0000-0002": RuntimeError("rusak")})
    with pytest.raises(annoter_pipeline.AnnotationFailure):
        annoter_pipeline.run(root)


def test_terlalu_banyak_blok_gagal_melempar_error(window_names, make_windows, patch_annotate, window_result):
    root = make_windows(window_names[:2])
    patch_annotate({"p0000-0002": window_result(failed=2, attempted=3), "p0003-0005": window_result(failed=0, attempted=3)})
    with pytest.raises(annoter_pipeline.AnnotationFailure, match="blok"):
        annoter_pipeline.run(root)


def test_ambang_tepat_tiga_puluh_persen_masih_lolos(window_names, make_windows, patch_annotate, window_result):
    root = make_windows(window_names[:1])
    patch_annotate({"p0000-0002": window_result(failed=3, attempted=10)})
    assert len(annoter_pipeline.run(root)) == 1


def test_sedikit_blok_gagal_hanya_peringatan(window_names, make_windows, patch_annotate, window_result, caplog):
    root = make_windows(window_names[:2])
    patch_annotate({"p0000-0002": window_result(failed=1, attempted=10), "p0003-0005": window_result(failed=0, attempted=10)})
    with caplog.at_level("WARNING", logger="annoter"):
        assert len(annoter_pipeline.run(root)) == 2
    assert "blok gagal: 1 dari 20" in caplog.text


def test_tanpa_window_mengembalikan_daftar_kosong(tmp_path):
    assert annoter_pipeline.run(tmp_path) == []


def test_run_with_report_membawa_jumlah_gagal(window_names, make_windows, patch_annotate, window_result):
    root = make_windows(window_names[:2])
    patch_annotate({"p0000-0002": window_result(failed=1, attempted=10), "p0003-0005": window_result(failed=0, attempted=10)})
    report = annoter_pipeline.run_with_report(root)
    assert (len(report.paths), report.failed_blocks, report.attempted, report.failed_windows, report.needs_review) == (2, 1, 20, [], 1)


def test_run_tetap_mengembalikan_daftar_path(window_names, make_windows, patch_annotate, window_result):
    root = make_windows(window_names[:1])
    patch_annotate({"p0000-0002": window_result()})
    assert [p.parent.name for p in annoter_pipeline.run(root)] == ["p0000-0002"]


def test_breaker_dibagi_antar_window_dan_pipeline_berhenti_cepat(systemic_error, window_names, make_windows, monkeypatch):
    root = make_windows(window_names[:3])
    seen = []

    def annotate_window(path, breaker=None):
        seen.append(path.parent.name)
        for _ in range(annoter_pipeline.config.BREAKER_THRESHOLD):
            breaker.failure(systemic_error())
        return WindowResult([Annotated("text", 0, 0, "isi")], 5, 100)

    monkeypatch.setattr(annoter_pipeline.annotate, "annotate_window", annotate_window)
    with pytest.raises(annoter_pipeline.AnnotationFailure, match="layanan LLM tidak tersedia"):
        annoter_pipeline.run_with_report(root)
    assert seen == ["p0000-0002"]
    assert (root / "p0000-0002" / "annotated.json").exists()


def test_main_folder_tidak_ada_mengembalikan_2(tmp_path, capsys):
    assert annoter_pipeline.main(["--outputs", str(tmp_path / "tidak-ada")]) == 2
    assert "folder output tidak ada" in capsys.readouterr().err


def test_main_melaporkan_jumlah_file(window_names, make_windows, patch_annotate, window_result, capsys):
    root = make_windows(window_names[:1])
    patch_annotate({"p0000-0002": window_result()})
    assert annoter_pipeline.main(["--outputs", str(root)]) == 0
    assert "Total 1 file JSON" in capsys.readouterr().out
