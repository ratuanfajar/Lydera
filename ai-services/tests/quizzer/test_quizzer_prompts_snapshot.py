import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from quizzer import config, prompts

SNAPSHOT = json.loads((Path(__file__).parent / "prompts_snapshot.json").read_text(encoding="utf-8"))
POINT = {"kind": "rumus", "text": "Poin contoh."}
SOAL = {
    "question_text": "Soal?", "options": {"A": "a", "B": "b", "C": "c", "D": "d"}, "correct_option": "B",
    "langkah": ["l1", "l2"], "kesimpulan": "k",
}
SEGMENT = SimpleNamespace(context_text="konteks", labeled_text="[1] isi")
CHAPTERS = [{"chapter_id": 1, "cp_text": "CP", "quota": {3: 2, 5: 1}, "points": [{"id": "p1", "kind": "rumus", "text": "t"}]}]


MODES = ("off", "on", "teks")
TYPED_SPEC = {"svg": "<svg viewBox=\"0 0 10 10\"><rect width=\"5\" height=\"5\"/></svg>", "deskripsi": "Satu persegi."}


def rendered(mode: str = "off") -> dict:
    items = {
        "GENERATE_SYSTEM": prompts.GENERATE_SYSTEM,
        "STIMULUS_INSTRUCTION": prompts.STIMULUS_INSTRUCTION,
        "REVISE_SOAL_SYSTEM": prompts.REVISE_SOAL_SYSTEM,
        "REVISE_STIMULUS_SYSTEM": prompts.REVISE_STIMULUS_SYSTEM,
        "RECHECK_SOAL_SYSTEM": prompts.RECHECK_SOAL_SYSTEM,
        "VALIDATE_SYSTEM": prompts.VALIDATE_SYSTEM,
        "AUDIT_SYSTEM": prompts.AUDIT_SYSTEM,
        "POINTS_SYSTEM": prompts.POINTS_SYSTEM,
        "MAPPING_SYSTEM": prompts.MAPPING_SYSTEM,
        "generate_input_c3": prompts.generate_input(POINT, "sumber", 3, "CP", ""),
        "generate_input_c5": prompts.generate_input(POINT, "sumber", 5, "CP", "koreksi"),
        "generate_input_visual": prompts.generate_input(POINT, "sumber", 4, "CP", "", ("image", "table")),
        "validate_input": prompts.validate_input("sumber", "Soal?", SOAL["options"], "stimulus"),
        "audit_input": prompts.audit_input("sumber", SOAL, "stimulus", "markup"),
        "format_soal": prompts.format_soal(SOAL),
        "revise_soal_input": prompts.revise_soal_input("sumber", "stimulus", SOAL, "feedback"),
        "revise_stimulus_input": prompts.revise_stimulus_input("sumber", "stimulus", "feedback"),
        "recheck_soal_input": prompts.recheck_soal_input("sumber", "stimulus baru", SOAL),
        "points_input": prompts.points_input(SEGMENT),
        "mapping_input": prompts.mapping_input(CHAPTERS),
    }
    items["REVISE_STIMULUS_TYPED_SYSTEM"] = prompts.REVISE_STIMULUS_TYPED_SYSTEM
    items["revise_stimulus_typed_input"] = prompts.revise_stimulus_typed_input("sumber", "stimulus", "gambar", TYPED_SPEC, "feedback")
    return items


@pytest.fixture
def configure(monkeypatch):
    def apply(mode: str) -> None:
        monkeypatch.setenv("QUIZ_MARKUP_ENABLED", "0" if mode == "off" else "")
        monkeypatch.setenv("QUIZ_STIMULUS_TYPES", "teks" if mode == "teks" else "")
        importlib.reload(config)
        importlib.reload(prompts)

    yield apply
    monkeypatch.undo()
    importlib.reload(config)
    importlib.reload(prompts)


@pytest.mark.parametrize("mode, name", [(mode, name) for mode in SNAPSHOT for name in sorted(SNAPSHOT[mode])])
def test_prompt_identik_dengan_snapshot(configure, mode, name):
    configure(mode)
    assert rendered(mode)[name] == SNAPSHOT[mode][name]


@pytest.mark.parametrize("mode", sorted(SNAPSHOT))
def test_tidak_ada_prompt_yang_hilang_atau_bertambah(configure, mode):
    configure(mode)
    assert set(rendered(mode)) == set(SNAPSHOT[mode])
