from collections import Counter

import pytest

from quizzer import mapping

KINDS = ["definisi", "rumus", "prosedur", "miskonsepsi", "perbandingan", "aplikasi", "konsep"]


def make_points(count, chapter=1):
    return [
        {
            "id": f"c{chapter}p{i}", "kind": KINDS[i % len(KINDS)], "text": f"poin {i}", "segment_index": i // 3,
            "order_start": i * 10, "order_end": i * 10 + 5, "quote": "", "chapter_id": chapter,
        }
        for i in range(count)
    ]


def make_chapter(chapter_id, count, lots, hots):
    return {"chapter_id": chapter_id, "cp_text": "cp", "lots_count": lots, "hots_count": hots, "points": make_points(count, chapter_id)}


def bad_proposal(chapters):
    return {1: {3: ["zzz", "c1p0", "c1p0"], 4: ["c1p3"]}}


@pytest.fixture
def planned():
    chapters = [make_chapter(1, 12, 6, 4), make_chapter(2, 3, 5, 3), make_chapter(3, 0, 2, 2)]
    slots, notes = mapping.plan_slots(chapters, bad_proposal)
    return chapters, slots, notes


def test_level_quota_membagi_lots_ke_tiga_level_dan_hots_ke_dua_level():
    quota = mapping.level_quota(7, 3, 0)
    assert sum(quota[level] for level in (1, 2, 3)) == 7
    assert sum(quota[level] for level in (4, 5)) == 3


def test_level_quota_offset_menggeser_level_penerima_sisa():
    assert mapping.level_quota(7, 3, 1) != mapping.level_quota(7, 3, 0)


def test_level_quota_nol_menghasilkan_kuota_nol_semua_level():
    assert mapping.level_quota(0, 0) == {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}


def test_plan_slots_memenuhi_kuota_setiap_bab_dan_level(planned):
    chapters, slots, _ = planned
    by_level = Counter((s["chapter_id"], s["level"]) for s in slots)
    for chapter in chapters[:2]:
        for level, need in chapter["quota"].items():
            assert by_level[(chapter["chapter_id"], level)] == need


def test_plan_slots_bab_tanpa_poin_tidak_menghasilkan_slot(planned):
    _, slots, _ = planned
    assert not any(s["chapter_id"] == 3 for s in slots)


def test_plan_slots_mencatat_poin_dipakai_ulang_bila_poin_kurang(planned):
    _, _, notes = planned
    assert notes[2]["reused_points"] >= 5


def test_plan_slots_tidak_memakai_ulang_poin_bila_poin_cukup(planned):
    _, slots, _ = planned
    ids = [s["point"]["id"] for s in slots if s["chapter_id"] == 1]
    assert len(ids) == len(set(ids))


def test_plan_slots_menyebar_slot_ke_banyak_segmen(planned):
    _, slots, _ = planned
    segments = {s["point"]["segment_index"] for s in slots if s["chapter_id"] == 1}
    assert len(segments) >= 3


def test_plan_slots_tanpa_usulan_memakai_pengisi_deterministik():
    slots, notes = mapping.plan_slots([make_chapter(1, 12, 3, 2)], lambda chapters: {})
    assert len(slots) == 5
    assert notes[1]["mapping"] == "pengisi"
