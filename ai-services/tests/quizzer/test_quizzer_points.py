import json

import pytest

from common import llm
from quizzer import config, points
from quizzer.segment import Segment


def block(order, text="isi"):
    return {"reading_order": order, "block_type": "text", "readable_text": text}


def make_segment(orders=(10, 20, 30, 40)):
    blocks = [block(o, f"teks {o}") for o in orders]
    return Segment(1, "Judul", orders[0], orders[-1], "\n".join(b["readable_text"] for b in blocks), "konteks", blocks)


@pytest.fixture
def store(monkeypatch):
    memory = {}
    monkeypatch.setattr(points.cache, "get", lambda namespace, *parts: memory.get((namespace, parts)))
    monkeypatch.setattr(points.cache, "put", lambda namespace, value, *parts: memory.__setitem__((namespace, parts), value))
    return memory


def raw(text="Poin satu.", kind="rumus", start=10, end=20, quote="kutipan"):
    return {"teks": text, "jenis": kind, "mulai": start, "selesai": end, "kutipan": quote}


def test_normalize_mengambil_field_dan_merapikan_rentang():
    [point] = points._normalize(make_segment(), [raw(start=30, end=10)])
    assert point == {"text": "Poin satu.", "kind": "rumus", "order_start": 10, "order_end": 30, "quote": "kutipan"}


def test_normalize_jenis_tidak_dikenal_menjadi_konsep_dan_nomor_blok_asing_memakai_batas_segmen():
    [point] = points._normalize(make_segment(), [raw(kind="aneh", start=999, end="x")])
    assert (point["kind"], point["order_start"], point["order_end"]) == ("konsep", 10, 40)


@pytest.mark.parametrize("bad", [None, "teks", 5, {"jenis": "rumus"}, {"teks": "   "}])
def test_normalize_membuang_butir_tidak_valid(bad):
    assert points._normalize(make_segment(), [bad]) == []


def test_normalize_daftar_bukan_list_menghasilkan_kosong():
    assert points._normalize(make_segment(), "bukan list") == []


def test_normalize_membatasi_kutipan_dan_jumlah_poin(monkeypatch):
    monkeypatch.setattr(config, "MAX_POINTS_PER_SEGMENT", 3)
    result = points._normalize(make_segment(), [raw(text=f"poin {i}", quote="k" * 500) for i in range(10)])
    assert len(result) == 3 and all(len(p["quote"]) == points.QUOTE_MAX_CHARS for p in result)


def point(text, segment_index=0, order=10):
    return {"text": text, "segment_index": segment_index, "order_start": order}


def test_dedupe_membuang_poin_mirip_pada_segmen_bertetangga():
    result = points.dedupe([point("rumus jarak dua titik pada bidang", 0), point("rumus jarak dua titik pada bidang koordinat", 1)])
    assert len(result) == 1


def test_dedupe_mempertahankan_poin_mirip_pada_segmen_berjauhan():
    first, far = point("rumus jarak dua titik pada bidang", 0), point("rumus jarak dua titik pada bidang", 5)
    assert points.dedupe([first, far]) == [first, far]


def test_dedupe_mempertahankan_poin_berbeda():
    items = [point("definisi fungsi", 0), point("grafik parabola membuka ke atas", 0)]
    assert points.dedupe(items) == items


def test_extract_segment_memanggil_llm_sekali_lalu_memakai_cache(store, monkeypatch):
    calls = []
    monkeypatch.setattr(points.llm, "complete_json", lambda *args, **kwargs: calls.append(1) or {"poin": [raw()]})
    first = points.extract_segment(make_segment())
    second = points.extract_segment(make_segment())
    assert first == second and len(calls) == 1


def test_extract_segment_keluaran_terpotong_dibagi_dua_lalu_digabung(store, monkeypatch):
    sizes = []

    def complete_json(system, user, **kwargs):
        sizes.append(len(user))
        if len(sizes) == 1:
            raise llm.TruncatedOutputError("terpotong")
        return {"poin": [raw(text=f"poin {len(sizes)}", start=10, end=10)]}

    monkeypatch.setattr(points.llm, "complete_json", complete_json)
    result = points.extract_segment(make_segment((10, 20, 30, 40)))
    assert [p["text"] for p in result] == ["poin 2", "poin 3"]


def test_extract_segment_terpotong_pada_satu_blok_melempar_error(store, monkeypatch):
    def complete_json(*args, **kwargs):
        raise llm.TruncatedOutputError("terpotong")

    monkeypatch.setattr(points.llm, "complete_json", complete_json)
    with pytest.raises(llm.TruncatedOutputError):
        points.extract_segment(make_segment((10,)))


def test_halves_membagi_blok_dan_memberi_konteks_dua_blok_terakhir_paruh_pertama():
    first, second = points._halves(make_segment((10, 20, 30, 40)))
    assert [b["reading_order"] for b in first.blocks] == [10, 20]
    assert [b["reading_order"] for b in second.blocks] == [30, 40]
    assert second.context_text == "teks 10\nteks 20"
    assert (second.reading_order_start, second.reading_order_end) == (30, 40)


def test_hasil_cache_berupa_json_valid(store, monkeypatch):
    monkeypatch.setattr(points.llm, "complete_json", lambda *args, **kwargs: {"poin": [raw()]})
    points.extract_segment(make_segment())
    [cached] = store.values()
    assert json.loads(cached)[0]["text"] == "Poin satu."
