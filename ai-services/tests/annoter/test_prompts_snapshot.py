import json
from pathlib import Path

import pytest

from annoter import prompts

SNAPSHOT = json.loads((Path(__file__).parent / "prompts_snapshot.json").read_text(encoding="utf-8"))


def rendered():
    items = {
        "table_system": prompts.table_system(),
        "table_system_feedback": prompts.table_system(feedback=True),
        "image_system": prompts.image_system(),
        "image_system_feedback": prompts.image_system(feedback=True),
        "classifier_system": prompts.image_classifier_system(),
        "arbiter_system": prompts.image_arbiter_system(),
        "table_input": prompts.table_input("Tabel 1", "<table></table>", "perbaiki"),
        "table_input_plain": prompts.table_input("Tabel 1", "<table></table>"),
        "image_input": prompts.image_input("Gambar 1", "teks sekitar", "perbaiki"),
        "image_input_plain": prompts.image_input("Gambar 1", "teks sekitar"),
        "classifier_input": prompts.image_classifier_input("Gambar 1", "teks sekitar"),
        "arbiter_input": prompts.image_arbiter_input("Gambar 1", "teks", {"jenis": "grafik", "yakin": 4}, {"jenis": "diagram", "yakin": 3}),
    }
    for kind in prompts.KIND_RULES:
        items[f"kind_{kind}"] = prompts.image_kind_system(kind)
        items[f"kind_{kind}_feedback"] = prompts.image_kind_system(kind, feedback=True)
    return items


@pytest.mark.parametrize("name", sorted(SNAPSHOT))
def test_prompt_identik_dengan_snapshot(name):
    if name == "image_kinds":
        assert list(prompts.IMAGE_KINDS) == SNAPSHOT[name]
    else:
        assert rendered()[name] == SNAPSHOT[name]


def test_tidak_ada_jenis_prompt_yang_hilang_atau_bertambah():
    expected = {name for name in SNAPSHOT if name != "image_kinds"}
    assert set(rendered()) == expected
