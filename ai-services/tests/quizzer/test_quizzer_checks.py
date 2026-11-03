import pytest

from quizzer import checks


@pytest.fixture
def good():
    return {
        "question_text": "q", "options": {"A": "aa", "B": "bb", "C": "cc", "D": "dd"}, "correct_option": "A",
        "langkah": ["l"], "kesimpulan": "k", "stimulus": None,
    }


def test_code_issues_kosong_untuk_soal_baik(good):
    assert checks.code_issues(good) == []


def test_option_length_issue_melaporkan_kunci_jauh_lebih_panjang(good):
    long = dict(good, options={"A": "a" * 100, "B": "bb", "C": "cc", "D": "dd"})
    assert checks.option_length_issue(long)


def test_code_issues_melaporkan_opsi_kurang_dari_empat(good):
    assert checks.code_issues(dict(good, options={"A": "x"}))


def test_code_issues_melaporkan_kunci_di_luar_opsi(good):
    assert checks.code_issues(dict(good, correct_option="Z"))


def test_code_issues_melaporkan_rujukan_gambar(good):
    assert checks.code_issues(dict(good, question_text="Perhatikan gambar berikut"))


def test_code_issues_mengizinkan_kata_diagram_tanpa_pola_rujukan(good):
    assert not checks.code_issues(dict(good, question_text="Himpunan A digambarkan dengan diagram Venn"))


@pytest.mark.parametrize(
    "override",
    [
        {"options": {"A": 1, "B": 2, "C": 3, "D": 4}},
        {"langkah": "satu langkah"},
        {"stimulus": "cerita"},
    ],
)
def test_structure_issues_melaporkan_tipe_data_tidak_valid(good, override):
    assert checks.structure_issues(dict(good, **override))


def test_code_issues_level_hots_tanpa_stimulus_dilaporkan(good):
    assert checks.code_issues(dict(good, stimulus=None), 4)


def test_code_issues_level_lots_dengan_stimulus_dilaporkan(good):
    assert checks.code_issues(dict(good, stimulus={"readable_text": "cerita"}), 2)


def test_code_issues_level_hots_dengan_stimulus_lolos(good):
    assert not checks.code_issues(dict(good, stimulus={"readable_text": "cerita"}), 4)


@pytest.mark.parametrize("field", ["question_text", "kesimpulan"])
def test_kata_stimulus_di_soal_atau_kesimpulan_ditolak(good, field):
    assert checks.code_issues(dict(good, **{field: "Berdasarkan stimulus, manakah yang benar?"}))


def test_kata_stimulus_di_opsi_atau_langkah_ditolak(good):
    assert checks.stimulus_word_issue(dict(good, options={**good["options"], "B": "Sesuai Stimulus itu"}))
    assert checks.stimulus_word_issue(dict(good, langkah=["Baca stimulus dahulu"]))


def test_acuan_tadi_dan_kata_mirip_tidak_ditolak(good):
    assert checks.stimulus_word_issue(dict(good, question_text="Berdasarkan tabel tadi, manakah yang benar?")) == []
    assert checks.stimulus_word_issue(dict(good, question_text="Rangsangan stimulasi saraf")) == []


def test_pada_gambar_ditolak_untuk_stimulus_teks_tetapi_boleh_untuk_stimulus_bertipe(good):
    teks = dict(good, question_text="Pada gambar lingkaran, manakah busur yang tepat?", stimulus={"readable_text": "x"})
    assert checks.references_visual(teks)
    tanpa = dict(good, question_text="Dalam gambar, berapakah nilainya?")
    assert checks.references_visual(tanpa)
    typed = dict(good, question_text="Pada gambar tadi, berapakah nilainya?",
                 stimulus={"jenis": "gambar", "spesifikasi": {"svg": "<svg/>"}, "readable_text": "x"})
    assert not checks.references_visual(typed)
    assert not checks.references_visual(dict(good, question_text="Pada diagram panah, relasi disebut fungsi bila ..."))


@pytest.mark.parametrize("question, expected", [
    ("Langkah awal untuk mencari invers adalah...", "Langkah awal untuk mencari invers adalah apa?"),
    ("Hasil akhirnya yaitu ...", "Hasil akhirnya yaitu apa?"),
    ("Penilaian yang paling tepat terhadap klaim itu ...", "Penilaian yang paling tepat terhadap klaim itu?"),
    ("Kesimpulan yang tepat adalah …", "Kesimpulan yang tepat adalah apa?"),
])
def test_soal_menggantung_diperbaiki_menjadi_pertanyaan_lengkap(good, question, expected):
    fixed = checks.repair_dangling_question(dict(good, question_text=question))
    assert fixed["question_text"] == expected and checks.dangling_question_issue(fixed) == []


def test_soal_tanpa_titik_di_ujung_tidak_diubah(good):
    data = dict(good, question_text="Berapa hasilnya?")
    assert checks.repair_dangling_question(data) is data
