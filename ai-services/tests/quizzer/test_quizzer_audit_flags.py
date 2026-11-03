from quizzer import validate


def audit(**changes):
    base = {
        "langkah_valid": True, "kesimpulan_konsisten": True, "opsi_lain_benar": [], "stem_ambigu": False, "data_lengkap": True,
        "opsi_di_luar_soal": False, "opsi_kontradiktif": False, "masalah": [],
    }
    return {**base, **changes}


def issues(audit_result):
    return validate.verification_issues({"correct_option": "A"}, {"matches": True}, audit_result, False)


def test_penanda_audit_menambah_temuan_dari_hasil_audit():
    assert len(issues(audit(data_lengkap=False, opsi_di_luar_soal=True, opsi_kontradiktif=True))) == 3


def test_audit_bersih_tidak_menghasilkan_temuan():
    assert issues(audit()) == []


def test_audit_tanpa_penanda_baru_tetap_kompatibel():
    assert issues({"masalah": []}) == []
