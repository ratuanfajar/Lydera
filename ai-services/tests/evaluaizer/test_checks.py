import pytest

from evaluaizer import checks, evaluate

STEPS = 3
OPTIONS = 2


@pytest.fixture
def good():
    return {
        "divergence_step": 2,
        "error_type": "salah_hitung",
        "diagnosis": "Kesalahan hitung di langkah dua.",
        "justification_points": [
            {"point": "Langkah pertama sudah benar.", "step_ref": 1, "is_divergence": False},
            {"point": "Jawaban benar adalah lima.", "step_ref": None, "is_divergence": True},
        ],
    }


def issues(result, steps=STEPS):
    return checks.result_issues(result, steps, OPTIONS)


def with_points(result, points):
    return dict(result, justification_points=points)


def points_with_first(point, **extra):
    return [dict(point=point, **extra), {"point": "b", "step_ref": None}]


def test_result_issues_hasil_valid_tanpa_masalah(good):
    assert issues(good) == []


@pytest.mark.parametrize(
    "override",
    [
        {"divergence_step": 4},
        {"divergence_step": 0},
        {"divergence_step": True},
        {"error_type": "ngawur"},
        {"diagnosis": " "},
        {"justification_points": []},
        {"justification_points": "x"},
    ],
)
def test_result_issues_menolak_field_tidak_valid(good, override):
    assert issues(dict(good, **override))


@pytest.mark.parametrize(
    "points",
    [
        [{"point": "a", "step_ref": 3}, {"point": "b", "step_ref": None}],
        [{"point": "", "step_ref": None}, {"point": "b", "step_ref": None}],
        [{"point": "x" * 500, "step_ref": None}, {"point": "b", "step_ref": None}],
        ["teks", "teks"],
        points_with_first("Hasilnya x = 3 + 4", step_ref=None),
        points_with_first("**Tebal** kata", step_ref=None),
        points_with_first("Catatan langkah siswa tidak disertakan.", step_ref=None),
    ],
)
def test_result_issues_menolak_poin_tidak_valid(good, points):
    assert issues(with_points(good, points))


def test_result_issues_menerima_kata_langkah_kamu_pada_poin_divergensi(good):
    points = points_with_first("Langkah kamu tidak tepat di bagian ini.", step_ref=None, is_divergence=True)
    assert issues(with_points(good, points)) == []


def test_result_issues_tanpa_langkah_siswa_menerima_divergensi_kosong(good):
    none = dict(good, divergence_step=None, error_type="tanpa_langkah")
    assert issues(none, steps=0) == []


def test_result_issues_tanpa_langkah_siswa_menolak_divergensi_berisi(good):
    assert issues(dict(good), steps=0)


def test_result_issues_tanpa_langkah_menolak_bila_siswa_punya_langkah(good):
    none = dict(good, divergence_step=None, error_type="tanpa_langkah")
    assert issues(none)


@pytest.mark.parametrize(
    "points",
    [
        [{"point": "a", "step_ref": None, "is_divergence": False}, {"point": "b", "step_ref": None, "is_divergence": False}],
        [{"point": "a", "is_divergence": True}, {"point": "b", "is_divergence": True}],
        [{"point": "a", "is_divergence": "ya"}, {"point": "b", "is_divergence": True}],
        [{"point": "Kamu memakai penjumlahan вместо perkalian", "is_divergence": True}, {"point": "b"}],
        [{"point": "Nilai 3x dipakai", "is_divergence": True}, {"point": "b"}],
        [{"point": "Sesuai langkah kunci pertama.", "is_divergence": True}, {"point": "b"}],
    ],
)
def test_result_issues_menolak_penanda_divergensi_dan_teks_bermasalah(good, points):
    assert issues(with_points(good, points))


@pytest.mark.parametrize("point", ["Opsi B, yaitu Rp150.000, benar.", "Harganya 150.000 rupiah"])
def test_result_issues_menerima_angka_dan_opsi_pada_poin_divergensi(good, point):
    points = [{"point": point, "is_divergence": True}, {"point": "b"}]
    assert issues(with_points(good, points)) == []


def test_normalize_mengubah_nomor_langkah_string_menjadi_int():
    normalized = evaluate._normalize({"divergence_step": "2", "justification_points": [{"point": "p", "step_ref": "1"}, "bukan dict"]})
    assert normalized["divergence_step"] == 2
    assert normalized["justification_points"][0]["step_ref"] == 1


def test_finish_membersihkan_poin_dan_menandai_perlu_review(good):
    result = dict(
        good,
        error_type="ngawur",
        justification_points=[
            {"point": " satu ", "step_ref": "x", "is_divergence": True},
            {"point": "", "step_ref": 1},
            {"point": "dua", "step_ref": 9},
        ],
    )
    finished = evaluate._finish(result, ["masalah"], STEPS, OPTIONS)
    assert finished["error_type"] == "lainnya"
    assert finished["needs_review"] is True
    assert finished["justification_points"] == [
        {"point": "satu", "step_ref": None, "is_divergence": True},
        {"point": "dua", "step_ref": None, "is_divergence": False},
    ]
    assert finished["personalized_justification"] == "Poin satu. satu Poin dua. dua"


def test_finish_membuang_nomor_langkah_di_luar_jangkauan(good):
    assert evaluate._finish(dict(good, divergence_step=9), [], STEPS, OPTIONS)["divergence_step"] is None


@pytest.mark.parametrize("empty", [[], "x", [{"point": " "}]])
def test_finish_gagal_bila_tidak_ada_poin_valid(good, empty):
    with pytest.raises(ValueError):
        evaluate._finish(dict(good, justification_points=empty), [], STEPS, OPTIONS)
