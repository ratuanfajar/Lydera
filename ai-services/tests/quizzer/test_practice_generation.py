import random

import pytest

from quizzer import quizzer_pipeline


def candidate(valid=True, repair=(), flag=(), stimulus=None):
    return {"data": {"stimulus": stimulus, "question_text": "q"}, "valid": valid, "repair": list(repair), "flag": list(flag)}


@pytest.fixture
def attempts(monkeypatch):
    calls = []

    def install(*outcomes):
        queue = list(outcomes)

        def fake(slot, chapter, source, correction, last, visuals=()):
            calls.append({"slot": slot, "source": source, "correction": correction, "last": last})
            outcome = queue.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        monkeypatch.setattr(quizzer_pipeline, "_attempt", fake)
        return calls

    return install


def run(level=2):
    return quizzer_pipeline.generate_practice("keliling", "sumber", level, random.Random(1))


def test_soal_bersih_langsung_dipakai_dan_verifikasi_tidak_dilonggarkan(attempts):
    calls = attempts(candidate())
    result = run()
    assert result["soal"]["question_text"] == "q" and result["issues"] == []
    assert len(calls) == 1 and calls[0]["last"] is False and calls[0]["source"] == "sumber"


def test_temuan_apa_pun_memicu_satu_perbaikan_lalu_lolos(attempts):
    calls = attempts(candidate(flag=["Stem ambigu."]), candidate())
    assert run()["soal"] is not None
    assert len(calls) == 2 and "Stem ambigu." in calls[1]["correction"]


def test_temuan_yang_bertahan_menolak_soal(attempts):
    attempts(candidate(flag=["Stem ambigu."]), candidate(repair=["Opsi B juga benar."]))
    result = run()
    assert result["soal"] is None and result["issues"] == ["Opsi B juga benar."]


def test_tidak_valid_walau_tanpa_temuan_ditolak(attempts):
    attempts(candidate(valid=False), candidate(valid=False))
    assert run()["soal"] is None


def test_stimulus_bertipe_ditolak(attempts):
    typed = {"jenis": "tabel", "spesifikasi": {"judul": "t", "kolom": ["a"], "baris": [["1"]]}}
    attempts(candidate(stimulus=typed), candidate(stimulus=typed))
    result = run()
    assert result["soal"] is None and quizzer_pipeline.PRACTICE_TYPED_ISSUE in result["issues"]


def test_stimulus_teks_diterima(attempts):
    attempts(candidate(stimulus={"readable_text": "Teks.", "source_markup": ""}))
    assert run()["soal"] is not None


def test_kegagalan_model_menjadi_penolakan_bukan_pengecualian(attempts):
    attempts(RuntimeError("model mati"), RuntimeError("model mati"))
    result = run()
    assert result["soal"] is None and "RuntimeError" in result["issues"][0]


def test_pulih_dari_satu_kegagalan(attempts):
    attempts(RuntimeError("sekali"), candidate())
    assert run()["soal"] is not None


@pytest.mark.parametrize("level,expected", [(0, 1), (2, 2), (5, 3)])
def test_level_dibatasi_ke_lots(attempts, level, expected):
    calls = attempts(candidate())
    run(level)
    assert calls[0]["slot"]["level"] == expected
