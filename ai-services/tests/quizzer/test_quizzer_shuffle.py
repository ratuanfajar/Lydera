import copy
import random
from collections import Counter

import pytest

from quizzer import shuffle


def soal(correct="B"):
    return {
        "options": {"A": "satu", "B": "dua", "C": "tiga", "D": "empat"}, "correct_option": correct,
        "langkah": ["Karena opsi B benar, pilih jawaban B."], "kesimpulan": "Jadi opsi B atau pilihan C.",
    }


@pytest.mark.parametrize("count", [0, 1, 3, 4, 9, 10])
def test_balanced_targets_menyebar_merata(count):
    targets = shuffle.balanced_targets(count, random.Random(1))
    assert len(targets) == count
    counts = Counter(targets)
    assert max(counts.values(), default=0) - min(counts.values(), default=0) <= 1 or count < 4


def test_balanced_targets_hanya_memakai_label_a_sampai_d():
    assert set(shuffle.balanced_targets(20, random.Random(2))) <= set("ABCD")


@pytest.mark.parametrize("target", list("ABCD"))
def test_reorder_options_menaruh_kunci_pada_target_tanpa_mengubah_isi(target):
    data = shuffle.reorder_options(soal(), target, random.Random(3))
    assert data["correct_option"] == target
    assert data["options"][target] == "dua"
    assert sorted(data["options"].values()) == ["dua", "empat", "satu", "tiga"]


def test_reorder_options_memetakan_ulang_huruf_pada_langkah_dan_kesimpulan():
    data = shuffle.reorder_options(soal(), "D", random.Random(3))
    assert "opsi D benar" in data["langkah"][0] and "jawaban D" in data["langkah"][0]
    new_c = [label for label, text in data["options"].items() if text == "tiga"][0]
    assert data["kesimpulan"] == f"Jadi opsi D atau pilihan {new_c}."


def test_reorder_options_memetakan_ulang_markup():
    data = soal()
    data["markup"] = {
        "options": {"A": "$a$", "B": "$b$", "C": "$c$", "D": "$d$"}, "langkah": ["opsi B benar"], "kesimpulan": "jawaban B",
    }
    result = shuffle.reorder_options(data, "A", random.Random(4))
    assert result["markup"]["options"]["A"] == "$b$"
    assert result["markup"]["langkah"] == ["opsi A benar"] and result["markup"]["kesimpulan"] == "jawaban A"


@pytest.mark.parametrize("mutation", [{"options": {"A": "x", "B": "y"}}, {"correct_option": "Z"}])
def test_reorder_options_membiarkan_soal_tidak_valid(mutation):
    data = {**soal(), **mutation}
    before = copy.deepcopy(data)
    assert shuffle.reorder_options(data, "C", random.Random(5)) == before


def test_remap_letters_tidak_menyentuh_huruf_di_luar_rujukan_opsi():
    mapping = {"A": "B", "B": "A", "C": "C", "D": "D"}
    assert shuffle._remap_letters("Titik A dan opsi A, B", mapping) == "Titik A dan opsi B, A"


def test_rujukan_huruf_tanpa_kata_opsi_atau_jawaban_baku_tidak_dipetakan_ulang():
    mapping = {"A": "B", "B": "A", "C": "C", "D": "D"}
    assert shuffle._remap_letters("Jadi jawabannya B.", mapping) == "Jadi jawabannya B."
