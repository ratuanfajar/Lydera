import importlib

import pytest

from quizzer import checks, config, prompts

SAMPLE_TERMS = (
    "komposisi", "invers", "busur", "singgung", "diskon", "bensin", "bahan bakar", "tempe", "mercusuar", "navigator",
    "f dari x", "sinus", "kosinus", "pythagoras", "kilometer", "rupiah", "raka", "nyoman", "sinta", "budi", "ardi",
)


@pytest.fixture(params=["0", ""])
def reloaded(request, monkeypatch):
    monkeypatch.setenv("QUIZ_MARKUP_ENABLED", request.param)
    monkeypatch.setenv("QUIZ_STIMULUS_TYPES", "")
    importlib.reload(config)
    importlib.reload(prompts)
    yield prompts
    monkeypatch.undo()
    importlib.reload(config)
    importlib.reload(prompts)


def prompt_texts(module) -> dict[str, str]:
    return {
        name: value for name, value in vars(module).items()
        if name.isupper() and isinstance(value, str) and name not in {"JSON_ONLY"}
    } | {f"bloom_{level}": text for level, text in module.BLOOM_GUIDANCE.items()}


def test_prompt_quizzer_tidak_memuat_istilah_atau_contoh_materi_sampel(reloaded):
    found = {
        name: [term for term in SAMPLE_TERMS if term in text.lower()]
        for name, text in prompt_texts(reloaded).items()
    }
    assert {name: terms for name, terms in found.items() if terms} == {}


def test_pesan_koreksi_pemeriksa_tidak_memuat_contoh_materi_sampel():
    message = checks.raw_symbol_issue({"question_text": "f(x) = 2x + 3", "options": {}, "langkah": [], "kesimpulan": "k"})[0]
    assert not any(term in message.lower() for term in SAMPLE_TERMS)


def test_skema_stimulus_tidak_memuat_istilah_materi_sampel():
    from quizzer.stimulus import registry

    schemas = registry.prompt_schemas().lower()
    assert [term for term in SAMPLE_TERMS if term in schemas] == []


def test_petunjuk_visual_hanya_untuk_hots_dan_memuat_hanya_jenis_yang_ditawarkan(monkeypatch, fake_vision):
    monkeypatch.setattr(config, "STIMULUS_TYPES", ("*",))
    point = {"kind": "rumus", "text": "poin"}
    with_hint = prompts.generate_input(point, "sumber", 4, "", "", ("image", "table"))
    assert "SOURCE VISUALS" in with_hint and "gambar" in with_hint
    assert "SOURCE VISUALS" not in prompts.generate_input(point, "sumber", 3, "", "", ("image",))
    assert "SOURCE VISUALS" not in prompts.generate_input(point, "sumber", 4, "", "", ())
    monkeypatch.setattr(config, "STIMULUS_TYPES", ("teks",))
    assert "SOURCE VISUALS" not in prompts.generate_input(point, "sumber", 4, "", "", ("image",))
