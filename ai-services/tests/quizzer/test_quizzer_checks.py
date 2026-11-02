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
