import pytest

from evaluaizer import checks

STEPS = ["Panjang dikali lebar.", "Dua belas kali lima sama dengan enam puluh.", "Jadi enam puluh."]


@pytest.fixture
def good():
    return {
        "penilaian_langkah": v(False, False, False), "dapat_ditentukan": True, "langkah_ke": 1, "kutipan": "Panjang dikali lebar.",
        "keterangan": "Pada langkah pertama, panjang dikalikan lebar sehingga menghasilkan luas, bukan keliling.",
    }


def v(*flags):
    return list(flags)


def issues(result, steps=STEPS):
    return checks.result_issues(result, steps)


def test_hasil_valid_tanpa_masalah(good):
    assert issues(good) == []


def test_tidak_dapat_ditentukan_valid_bila_langkah_dan_kutipan_kosong():
    result = {"penilaian_langkah": None, "dapat_ditentukan": False, "langkah_ke": None, "kutipan": None, "keterangan": "Hanya tertulis satu bilangan, letak kesalahan tidak dapat ditentukan."}
    assert issues(result, ["15"]) == []


def test_semua_langkah_benar_valid_dengan_langkah_ke_kosong():
    result = {"penilaian_langkah": v(True, True, True), "dapat_ditentukan": True, "langkah_ke": None, "kutipan": None, "keterangan": "Langkah siswa sesuai, tetapi opsi yang dipilih berbeda dari hasilnya."}
    assert issues(result) == []


@pytest.mark.parametrize("override", [
    {"dapat_ditentukan": "ya"},
    {"dapat_ditentukan": False},
    {"langkah_ke": 0},
    {"langkah_ke": 4},
    {"langkah_ke": True},
    {"kutipan": None},
    {"kutipan": ""},
    {"kutipan": "Luas dikali lebar."},
    {"langkah_ke": None},
    {"keterangan": ""},
    {"keterangan": "a" * 600},
])
def test_struktur_salah_dilaporkan(good, override):
    assert issues({**good, **override})


def test_kutipan_boleh_berupa_potongan_dan_beda_spasi_atau_tanda_baca(good):
    assert issues({**good, "kutipan": "panjang   dikali lebar"}) == []
    assert issues({**good, "penilaian_langkah": v(True, False, False), "langkah_ke": 2, "kutipan": "dua belas kali lima"}) == []


@pytest.mark.parametrize("text", [
    "Langkah menulis 3x sama dengan lima belas.",
    "Langkah menulis x = 3 padahal seharusnya lima.",
    "Langkah ini memakai **tebal** pada hasilnya.",
    "Apakah hasilnya sudah benar?",
    "Hasil pembagian tiga belas belas dibaca keliru.",
    "Langkah kunci menyebut hasil lima.",
    "Langkah ini memuat kata Yunani α di hasil.",
])
def test_keterangan_bermasalah_ditolak(good, text):
    assert issues({**good, "keterangan": text})


def test_kata_ulang_yang_wajar_tidak_ditolak(good):
    assert issues({**good, "keterangan": "Dua belas kali lima sama dengan enam puluh, bukan sama dengan lima puluh."}) == []


def test_kutipan_dengan_awalan_nomor_langkah_tetap_dianggap_berdasar(good):
    assert issues({**good, "kutipan": "1. Panjang dikali lebar."}) == []
    assert checks.strip_numbering("3) Terus dua ratus") == "Terus dua ratus"


def test_keterangan_tak_dapat_ditentukan_boleh_menyebut_tidak_ada_langkah_perhitungan():
    result = {"penilaian_langkah": None, "dapat_ditentukan": False, "langkah_ke": None, "kutipan": None,
              "keterangan": "Tertulis x nya tiga tanpa menunjukkan proses; tidak ada langkah perhitungan sehingga letak kesalahan tidak dapat ditentukan."}
    assert issues(result, ["Langsung ketemu x nya 3."]) == []


@pytest.mark.parametrize("verdicts, step, quote", [
    (v(True, False, False), 3, "Jadi enam puluh."),
    (v(True, True, True), 1, "Panjang dikali lebar."),
    (v(False, True, True), None, None),
    (v(True, False), 2, "Dua belas kali lima sama dengan enam puluh."),
    (None, 1, "Panjang dikali lebar."),
    ([True, "salah", False], 3, "Jadi enam puluh."),
])
def test_langkah_ke_harus_konsisten_dengan_penilaian_langkah(good, verdicts, step, quote):
    assert issues({**good, "penilaian_langkah": verdicts, "langkah_ke": step, "kutipan": quote})


def test_langkah_ke_sama_dengan_false_pertama_valid(good):
    assert issues({**good, "penilaian_langkah": v(True, False, False), "langkah_ke": 2, "kutipan": "Dua belas kali lima"}) == []
