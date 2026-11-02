import threading

import pytest

from annoter import annotate, resilience
from annoter.preprocess import Block, Route, Segment
from common import llm


def image_block(order):
    return Block(Route.IMAGE, order, 0, caption="Gambar 1")


@pytest.fixture
def run(monkeypatch):
    def use(blocks, errors):
        calls = []

        def annotate_image(block, context):
            calls.append(block.order)
            error = errors.get(len(calls))
            if error:
                raise error
            return annotate.image.ImageAnnotation("geometri", "gambar biasa")

        monkeypatch.setattr(annotate, "preprocess", lambda path: blocks)
        monkeypatch.setattr(annotate.image, "annotate_image", annotate_image)
        monkeypatch.setattr(annotate.config, "LLM_MAX_WORKERS", 1)
        monkeypatch.setattr(annotate.annoter_config, "BREAKER_THRESHOLD", 3)
        return annotate.annotate_window("x_content_list.json"), calls

    return use


def test_breaker_sticky_setelah_trip_walau_ada_sukses_terlambat(systemic_error):
    breaker = resilience.Breaker(2)
    breaker.failure(systemic_error())
    breaker.failure(systemic_error())
    breaker.success()
    assert breaker.tripped


def test_breaker_tidak_trip_oleh_galat_non_sistemik():
    breaker = resilience.Breaker(2)
    for _ in range(5):
        breaker.failure(llm.ContentFilterError("ditolak"))
    assert not breaker.tripped


def test_breaker_aman_untuk_banyak_thread(systemic_error):
    breaker = resilience.Breaker(100)
    threads = [threading.Thread(target=lambda: [breaker.failure(systemic_error()) for _ in range(25)]) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert breaker.streak == 100 and breaker.tripped


def test_galat_kunci_azure_kosong_dianggap_sistemik():
    assert resilience.is_systemic(RuntimeError("AZURE_OPENAI_API_KEY dan AZURE_OPENAI_ENDPOINT belum diisi"))
    assert not resilience.is_systemic(RuntimeError("lain"))
    assert not resilience.is_systemic(llm.ContentFilterError("ditolak"))


def test_pemutus_rangkaian_menghentikan_panggilan_setelah_galat_sistemik_beruntun(run, systemic_error):
    result, calls = run([image_block(i) for i in range(8)], {1: systemic_error(), 2: systemic_error(), 3: systemic_error()})
    assert len(calls) == 3
    assert (result.failed, result.attempted) == (8, 8)
    assert all(b.readable_text == "" and b.review_priority == "high" for b in result.blocks)


def test_content_filter_tidak_memicu_pemutus(run):
    result, calls = run([image_block(i) for i in range(8)], {i: llm.ContentFilterError("ditolak") for i in range(1, 6)})
    assert len(calls) == 8
    assert result.failed == 5


def test_sukses_mereset_hitungan_galat_beruntun(run, systemic_error):
    errors = {1: systemic_error(), 2: systemic_error(), 4: systemic_error(), 5: systemic_error()}
    result, calls = run([image_block(i) for i in range(8)], errors)
    assert len(calls) == 8
    assert result.failed == 4


def test_galat_sistemik_pada_rumus_inline_naik_dan_dihitung(monkeypatch, systemic_error):
    def convert(latex):
        raise systemic_error()

    monkeypatch.setattr(annotate.formula, "convert_checked", convert)
    block = Block(Route.TEXT, 0, 0, text="Nilai $x$.", segments=[Segment(False, "Nilai "), Segment(True, "x"), Segment(False, ".")])
    monkeypatch.setattr(annotate, "preprocess", lambda path: [block])
    result = annotate.annotate_window("x_content_list.json")
    assert (result.failed, result.blocks[0].review_priority) == (1, "high")
