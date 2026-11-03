import random
import threading

import pytest

from common import llm
from common.resilience import Breaker
from quizzer import config, generate, quizzer_pipeline, validate

BLOCKS = [{"reading_order": i * 10, "block_type": "text", "readable_text": f"blok {i} " + "x" * 300} for i in range(60)]
CHAPTER = {"blocks": BLOCKS, "cp_text": ""}
KINDS = ["definisi", "rumus", "prosedur", "miskonsepsi", "perbandingan", "aplikasi"]


def extract(seg):
    return [
        {"text": f"poin {i}", "kind": KINDS[i % 6], "order_start": seg.reading_order_start,
         "order_end": seg.reading_order_start + 5, "quote": ""}
        for i in range(7)
    ]


def good_soal(point, level):
    return {
        "analisis_level": "x", "question_text": f"Soal {point['text']} level {level}",
        "options": {"A": "satu", "B": "dua", "C": "tiga", "D": "empat"}, "correct_option": "A",
        "langkah": ["langkah"], "kesimpulan": "k", "stimulus": {"readable_text": "s"} if level >= 4 else None,
        "bloom_level": level, "reading_order_start": point["order_start"], "reading_order_end": point["order_end"],
    }


@pytest.fixture(autouse=True)
def single_worker_and_verifier(monkeypatch):
    monkeypatch.setattr(quizzer_pipeline.common_config, "LLM_MAX_WORKERS", 1)
    monkeypatch.setattr(config, "BREAKER_THRESHOLD", 3)
    monkeypatch.setattr(validate, "verify_soal", lambda source, data, stimulus="": {"issues": [], "unavailable": []})


def chapters(lots=6, hots=0):
    return [{"chapter_id": 1, "blocks": BLOCKS, "cp_text": "", "hots_count": hots, "lots_count": lots}]


def run(extract_fn=extract):
    return quizzer_pipeline.compute_for_quiz(chapters(), seed=1, extract=extract_fn, propose=lambda c: {})


def test_galat_sistemik_beruntun_menghentikan_panggilan_generate_dan_menyebut_layanan_tidak_tersedia(monkeypatch, systemic_error):
    calls = []

    def failing(point, source_text, level, cp_text="", correction=""):
        calls.append(1)
        raise systemic_error()

    monkeypatch.setattr(generate, "generate_soal", failing)
    result = run()
    assert result["items"] == []
    assert len(calls) == 3 * 1
    errors = {f["error"] for f in result["report"]["chapters"][0]["failed"]}
    assert errors == {quizzer_pipeline.UNAVAILABLE_REASON}
    assert result["report"]["summary"]["failed"] == 6


def test_content_filter_tidak_memicu_pemutus(monkeypatch):
    calls = []

    def filtered(point, source_text, level, cp_text="", correction=""):
        calls.append(1)
        raise llm.ContentFilterError("ditolak")

    monkeypatch.setattr(generate, "generate_soal", filtered)
    result = run()
    assert len(calls) == 6 * config.MAX_GENERATIONS_PER_SLOT
    assert {f["error"] for f in result["report"]["chapters"][0]["failed"]} == {"Ditolak filter keamanan model."}


def test_sukses_di_antara_galat_mereset_hitungan(monkeypatch, systemic_error):
    state = {"n": 0}

    def alternating(point, source_text, level, cp_text="", correction=""):
        state["n"] += 1
        if state["n"] % 3:
            raise systemic_error()
        return good_soal(point, level)

    monkeypatch.setattr(generate, "generate_soal", alternating)
    result = run()
    assert len(result["items"]) > 0


def test_ekstraksi_poin_gagal_sistemik_dilaporkan_per_bab_dan_slot_tidak_dibuat(systemic_error):
    def failing_extract(seg):
        raise systemic_error()

    result = run(failing_extract)
    chapter = result["report"]["chapters"][0]
    assert result["items"] == []
    assert chapter["extraction_errors"] and all("Layanan model tidak tersedia" in e for e in chapter["extraction_errors"])
    assert chapter["skipped_reason"] == quizzer_pipeline.NO_POINTS_REASON


def test_kandidat_valid_dipertahankan_bila_pemutus_terbuka_pada_percobaan_kedua(monkeypatch):
    breaker = Breaker(1)
    point = {"id": "p1", "kind": "definisi", "text": "poin 1", "order_start": 0, "order_end": 5, "quote": "", "segment_index": 0}
    slot = {"chapter_id": 1, "level": 1, "point": point, "reused": False, "target": "B", "rng": random.Random(1)}
    state = {"n": 0}

    def generate_soal(point, source_text, level, cp_text="", correction=""):
        state["n"] += 1
        breaker.tripped = True
        data = good_soal(point, level)
        data["question_text"] = "Perhatikan gambar berikut"
        return data

    monkeypatch.setattr(generate, "generate_soal", generate_soal)
    result = quizzer_pipeline._run_slot_safe(slot, CHAPTER, breaker=breaker)
    assert state["n"] == 1 and result["item"] is not None


def test_pemutus_aman_untuk_banyak_pekerja(monkeypatch, systemic_error):
    monkeypatch.setattr(quizzer_pipeline.common_config, "LLM_MAX_WORKERS", 4)
    lock, calls = threading.Lock(), []

    def failing(point, source_text, level, cp_text="", correction=""):
        with lock:
            calls.append(1)
        raise systemic_error()

    monkeypatch.setattr(generate, "generate_soal", failing)
    result = run()
    assert result["items"] == [] and 3 <= len(calls) <= 6 * config.MAX_GENERATIONS_PER_SLOT


@pytest.mark.parametrize("error, message", [
    (RuntimeError("AZURE_OPENAI_API_KEY belum diisi"), "Layanan model tidak tersedia."),
    (quizzer_pipeline.QuizzerUnavailable("x"), "Layanan model tidak tersedia."),
    (llm.TruncatedOutputError("x"), "Keluaran model terpotong."),
    (llm.ContentFilterError("x"), "Ditolak filter keamanan model."),
    (KeyError("rahasia"), "Kesalahan saat memproses (KeyError)."),
])
def test_safe_error_memetakan_penyebab_tanpa_membocorkan_pesan_asli(error, message):
    assert quizzer_pipeline._safe_error(error) == message
