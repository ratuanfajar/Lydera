import pytest

from clarifier import fusion, lexical


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Apa itu fungsi invers dan bagaimana cara mencarinya?", ["fungsi", "invers", "mencarinya"]),
        ("sudut keliling lingkaran", ["sudut", "keliling", "lingkaran"]),
        ("apa itu", []),
        ("Fungsi FUNGSI fungsi", ["fungsi"]),
        ("x'; drop table--", ["drop", "table"]),
    ],
)
def test_lexical_tokens_membuang_kata_umum_dan_simbol(question, expected):
    assert lexical.lexical_tokens(question) == expected


def test_lexical_tokens_dibatasi_max_tokens():
    question = " ".join(f"kata{i}" for i in range(30))
    assert len(lexical.lexical_tokens(question)) == lexical.MAX_TOKENS


@pytest.mark.parametrize(
    ("rankings", "weights", "expected"),
    [
        ([[5, 6, 7], [], [7]], None, [7, 5, 6]),
        ([], None, []),
        ([[9], [8], [9]], None, [9, 8]),
        ([[1, 2], [2, 1]], [1.0, 0.25], [1, 2]),
        ([[1, 2], [2, 1]], [0.25, 1.0], [2, 1]),
        ([[1], [2]], [1.0, 2.0], [2, 1]),
    ],
)
def test_reciprocal_rank_fusion_mengurutkan_dengan_bobot(rankings, weights, expected):
    args = (rankings,) if weights is None else (rankings, weights)
    assert fusion.reciprocal_rank_fusion(*args) == expected


def test_reciprocal_rank_fusion_menghormati_limit():
    assert fusion.reciprocal_rank_fusion([[1, 2, 3]], limit=2) == [1, 2]


def test_reciprocal_rank_fusion_menempatkan_peringkat_berlawanan_di_bawah():
    assert fusion.reciprocal_rank_fusion([[1, 2, 3], [3, 2, 1]])[-1] == 2
