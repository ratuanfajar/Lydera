import pytest

from quizzer import validate

DATA = {"question_text": "Soal?", "options": {"A": "a", "B": "b", "C": "c", "D": "d"}, "correct_option": "B"}
GOOD_BLIND = {"matches": True, "derived_option": "B", "derived_langkah": []}
GOOD_AUDIT = {
    "langkah_valid": True, "kesimpulan_konsisten": True, "opsi_lain_benar": [], "stem_ambigu": False,
    "stimulus_dibutuhkan": None, "readable_setia": None, "masalah": [],
}


def issues(blind=GOOD_BLIND, audit=GOOD_AUDIT, has_stimulus=False):
    return validate.verification_issues(DATA, blind, audit, has_stimulus)


def test_soal_yang_lolos_semua_pemeriksaan_tanpa_masalah():
    assert issues() == []


def test_jawab_buta_berbeda_dari_kunci_ditandai_dengan_langkah_validator():
    blind = {"matches": False, "derived_option": "C", "derived_langkah": ["hitung", "pilih"]}
    [message] = issues(blind=blind)
    assert "C" in message and "B" in message and "hitung; pilih" in message


@pytest.mark.parametrize(
    "change, fragment",
    [
        ({"langkah_valid": False}, "Langkah penyelesaian"),
        ({"kesimpulan_konsisten": False}, "Kesimpulan"),
        ({"opsi_lain_benar": ["A", "C"]}, "Opsi A, C juga benar"),
        ({"stem_ambigu": True}, "Stem ambigu"),
        ({"readable_setia": False}, "tidak setia"),
        ({"masalah": ["ada yang salah"]}, "ada yang salah"),
    ],
)
def test_temuan_audit_menjadi_masalah(change, fragment):
    assert any(fragment in issue for issue in issues(audit={**GOOD_AUDIT, **change}))


def test_opsi_lain_benar_mengabaikan_kunci_dan_nilai_bukan_daftar():
    assert issues(audit={**GOOD_AUDIT, "opsi_lain_benar": ["B"]}) == []
    assert issues(audit={**GOOD_AUDIT, "opsi_lain_benar": "A"}) == []


def test_stimulus_tidak_dibutuhkan_hanya_ditandai_bila_soal_punya_stimulus():
    audit = {**GOOD_AUDIT, "stimulus_dibutuhkan": False}
    assert issues(audit=audit, has_stimulus=False) == []
    assert any("Stimulus tidak dibutuhkan" in i for i in issues(audit=audit, has_stimulus=True))


def test_galat_audit_tidak_menambah_masalah_tetapi_jawab_buta_tetap_dinilai():
    blind = {"matches": False, "derived_option": "A", "derived_langkah": []}
    assert len(issues(blind=blind, audit=RuntimeError("mati"))) == 1


def test_galat_jawab_buta_tidak_melempar():
    assert issues(blind=RuntimeError("mati")) == []


def test_verify_soal_mencatat_validator_yang_gagal_dan_tidak_melempar(monkeypatch):
    def fail(*args, **kwargs):
        raise TimeoutError("lambat")

    monkeypatch.setattr(validate, "validate_soal", fail)
    monkeypatch.setattr(validate, "audit_soal", lambda *args, **kwargs: GOOD_AUDIT)
    result = validate.verify_soal("sumber", DATA)
    assert result["unavailable"] == ["Jawab buta oleh validator tidak dapat dijalankan (TimeoutError)."]
    assert result["issues"] == []


def test_verify_soal_membandingkan_jawaban_validator_dengan_kunci(monkeypatch):
    monkeypatch.setattr(validate.llm, "complete_json", lambda system, user, **kwargs: {"correct_option": " b. ", "langkah": ["x"]})
    assert validate.validate_soal("sumber", "Soal?", DATA["options"], "B")["matches"] is True
    monkeypatch.setattr(validate.llm, "complete_json", lambda system, user, **kwargs: {"correct_option": "C"})
    assert validate.validate_soal("sumber", "Soal?", DATA["options"], "B")["matches"] is False


def test_markup_text_menggabungkan_markup_soal_dan_stimulus():
    data = {**DATA, "markup": {"question": "$x$"}, "stimulus": {"readable_text": "r", "source_markup": "$y$ dan tabel"}}
    text = validate.markup_text(data)
    assert '"question": "$x$"' in text and "$y$ dan tabel" in text
    assert validate.markup_text(DATA) == ""
