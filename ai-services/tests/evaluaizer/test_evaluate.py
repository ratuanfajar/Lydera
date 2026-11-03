import pytest

from evaluaizer import evaluate

ARGS = ("sumber", "", "Berapa keliling?", {"A": "34", "B": "60"}, "A", ["Dua kali jumlah.", "Hasilnya 34."], "Jadi 34.", "B")
GOOD = {
    "penilaian_langkah": [False, False], "dapat_ditentukan": True, "langkah_ke": 1, "kutipan": "Panjang dikali lebar.",
    "keterangan": "Pada langkah pertama, panjang dikalikan lebar sehingga menghasilkan luas, bukan keliling.",
}
BAD = {**GOOD, "keterangan": "Apakah ini sudah benar?"}


@pytest.fixture
def asks(monkeypatch):
    calls = []

    def install(*answers):
        queue = list(answers)

        def fake(user):
            calls.append(user)
            return dict(queue.pop(0))

        monkeypatch.setattr(evaluate, "_ask", fake)
        return calls

    return install


def run(steps=("Panjang dikali lebar.", "Dua belas kali lima sama dengan enam puluh.")):
    return evaluate.evaluate_scratchwork(*ARGS, list(steps))


def test_tanpa_langkah_tidak_memanggil_model(asks):
    calls = asks()
    with pytest.raises(ValueError):
        run(steps=())
    assert calls == []


def test_hasil_bersih_dipakai_langsung(asks):
    calls = asks(GOOD)
    result = run()
    assert len(calls) == 1
    assert result["langkah_ke"] == 1 and result["kutipan"] == "Panjang dikali lebar." and result["needs_review"] is False


def test_satu_perbaikan_dipakai_bila_lebih_sedikit_masalahnya(asks):
    calls = asks(BAD, GOOD)
    result = run()
    assert len(calls) == 2 and "masalah" in calls[1] and result["issues"] == [] and result["needs_review"] is False


def test_perbaikan_yang_gagal_memakai_hasil_pertama_dan_menandai_review(asks, monkeypatch):
    queue = [BAD]

    def fake(user):
        if queue:
            return dict(queue.pop(0))
        raise RuntimeError("model mati")

    monkeypatch.setattr(evaluate, "_ask", fake)
    result = run()
    assert result["needs_review"] is True and result["issues"]


def test_tidak_dapat_ditentukan_mengosongkan_langkah_dan_kutipan(asks):
    asks({"penilaian_langkah": None, "dapat_ditentukan": False, "langkah_ke": None, "kutipan": None, "keterangan": "Hanya tertulis satu bilangan, letak kesalahan tidak dapat ditentukan."})
    result = run(steps=("15",))
    assert result["dapat_ditentukan"] is False and result["langkah_ke"] is None and result["kutipan"] is None


def test_nomor_langkah_berbentuk_teks_dinormalkan(asks):
    asks({**GOOD, "langkah_ke": "1"})
    assert run()["langkah_ke"] == 1


def test_keterangan_kosong_menjadi_valueerror(asks):
    asks({**GOOD, "keterangan": ""}, {**GOOD, "keterangan": ""})
    with pytest.raises(ValueError):
        run()
