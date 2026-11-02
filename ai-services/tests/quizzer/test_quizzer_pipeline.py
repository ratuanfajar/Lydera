import threading
import random
from collections import Counter

import pytest

from quizzer import generate, quizzer_pipeline, validate

KINDS = ["definisi", "rumus", "prosedur", "miskonsepsi", "perbandingan", "aplikasi"]
SECRET_ERROR = "secret endpoint https://x.openai.azure.com key=abc"
LONG_PHRASE = "panjang " * 30

BLOCKS = [{"reading_order": i * 10, "block_type": "text", "readable_text": f"blok {i} " + "x" * 300} for i in range(60)]
CHAPTER = {"blocks": BLOCKS, "cp_text": ""}


def fake_generate(point, source_text, level, cp_text="", correction=""):
    base = {
        "analisis_level": "x", "question_text": f"Soal {point['text']} level {level} {correction[:10]}",
        "options": {"A": "satu", "B": "dua", "C": "tiga", "D": "empat"}, "correct_option": "A",
        "langkah": ["langkah"], "kesimpulan": "k", "stimulus": {"readable_text": "s"} if level >= 4 else None,
        "bloom_level": level, "reading_order_start": point["order_start"], "reading_order_end": point["order_end"],
    }
    if point["text"] == "poin 1" and not correction:
        base["question_text"] = "Perhatikan gambar berikut"
    return base


def extract(seg):
    return [
        {"text": f"poin {i}", "kind": KINDS[i % 6], "order_start": seg.reading_order_start,
         "order_end": seg.reading_order_start + 5, "quote": ""}
        for i in range(7)
    ]


class LockedCounter(Counter):
    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()

    def __getitem__(self, key):
        return super().__getitem__(key)

    def hit(self, key):
        with self.lock:
            self[key] += 1


@pytest.fixture
def calls(monkeypatch):
    counter = LockedCounter()

    def generate_soal(point, source_text, level, cp_text="", correction=""):
        counter.hit("gen")
        if point["text"] == "poin 2":
            raise RuntimeError("model error")
        return fake_generate(point, source_text, level, cp_text, correction)

    def verify_soal(source_text, data, stimulus_text=""):
        counter.hit("ver")
        issues = ["Opsi B juga benar."] if "poin 3" in data["question_text"] else []
        return {"issues": issues, "unavailable": []}

    monkeypatch.setattr(generate, "generate_soal", generate_soal)
    monkeypatch.setattr(validate, "verify_soal", verify_soal)
    return counter


@pytest.fixture
def run(calls):
    progress = []
    chapters = [
        {"chapter_id": 1, "blocks": BLOCKS, "cp_text": "cp", "hots_count": 2, "lots_count": 4},
        {"chapter_id": 2, "blocks": [], "cp_text": "", "hots_count": 1, "lots_count": 1},
    ]
    result = quizzer_pipeline.compute_for_quiz(
        chapters, on_progress=lambda: progress.append(1), seed=3, extract=extract, propose=lambda c: {},
    )
    return result, progress


@pytest.fixture
def slot():
    point = {"id": "p1", "kind": "definisi", "text": "poin 9", "order_start": 0, "order_end": 5, "quote": "", "segment_index": 0}
    return {"chapter_id": 1, "level": 1, "point": point, "reused": False, "target": "B", "rng": random.Random(1)}


def test_compute_for_quiz_bab_tanpa_blok_dilewati_dengan_alasan(run):
    (result, _) = run
    skipped = result["report"]["chapters"][1]
    assert skipped["skipped_reason"]
    assert skipped["generated"] == {"lots": 0, "hots": 0}


def test_compute_for_quiz_memanggil_progress_sekali_per_slot(run):
    _, progress = run
    assert len(progress) == 6


def test_compute_for_quiz_melaporkan_jumlah_diminta_per_bab(run):
    (result, _) = run
    assert result["report"]["chapters"][0]["requested"] == {"lots": 4, "hots": 2}


def test_compute_for_quiz_ringkasan_menjumlahkan_berhasil_dan_gagal_sama_dengan_slot(run):
    (result, _) = run
    summary = result["report"]["summary"]
    assert summary["generated"] + summary["failed"] == 6


def test_compute_for_quiz_ringkasan_tanpa_duplicate_check(run):
    (result, _) = run
    assert "duplicate_check" not in result["report"]["summary"]


def test_compute_for_quiz_menghitung_panggilan_generator_dan_verifier(run, calls):
    assert calls["gen"] == 8
    assert calls["ver"] == 5


def test_compute_for_quiz_temuan_verifier_hanya_menandai_tanpa_regenerasi(run):
    (result, _) = run
    flagged = [item for item in result["items"] if "Opsi B juga benar." in item["issues"]]
    assert flagged
    assert flagged[0]["review_priority"] == "high"
    assert not flagged[0]["repaired"]


def test_compute_for_quiz_item_tidak_membawa_slot(run):
    (result, _) = run
    assert all("slot" not in item for item in result["items"])


def test_run_slot_safe_mempertahankan_kandidat_pertama_bila_percobaan_kedua_gagal(monkeypatch, slot):
    state = {"n": 0}

    def flaky_generate(point, source_text, level, cp_text="", correction=""):
        state["n"] += 1
        if state["n"] == 2:
            raise RuntimeError(SECRET_ERROR)
        data = fake_generate(point, source_text, level, cp_text, correction)
        data["question_text"] = "Soal dengan opsi benar " + LONG_PHRASE
        data["options"]["A"] = "A " + LONG_PHRASE
        return data

    monkeypatch.setattr(generate, "generate_soal", flaky_generate)
    monkeypatch.setattr(validate, "verify_soal", lambda src, data, stim="": {"issues": [], "unavailable": ["Audit tidak dapat dijalankan (Timeout)."]})
    result = quizzer_pipeline._run_slot_safe(slot, CHAPTER)
    assert result["item"] is not None
    assert result["item"]["review_priority"] == "high"
    assert "jauh lebih panjang" in result["item"]["validation_notes"]


def test_run_slot_safe_membersihkan_pesan_galat_dari_rahasia(monkeypatch, slot):
    def always_fail(*args, **kwargs):
        raise RuntimeError(SECRET_ERROR)

    monkeypatch.setattr(generate, "generate_soal", always_fail)
    result = quizzer_pipeline._run_slot_safe(slot, CHAPTER)
    assert result["item"] is None
    assert "secret" not in result["error"]
    assert "azure" not in result["error"]
