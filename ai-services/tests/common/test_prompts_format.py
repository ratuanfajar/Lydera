import re

import pytest

from annoter import prompts as annoter_prompts
from clarifier import agent, retrieval_grader, scope_gate
from common import formula, guardrails, image_prompts
from evaluaizer import prompts as evaluaizer_prompts
from quizzer import prompts as quizzer_prompts

SECTIONS = ("# ROLE", "# TASK", "# RULES")
DOCUMENT_NAMES = re.compile(r"\b(spec(ifikasi)?\s*\d|adr\b|readme|claude\.md|findings|docs/|dokumentasi\s+proyek)", re.IGNORECASE)


def system_prompts() -> dict[str, str]:
    found = {
        "clarifier.agent": agent.SYSTEM_PROMPT,
        "clarifier.scope_gate": scope_gate.CLASSIFIER_SYSTEM,
        "clarifier.retrieval_grader": retrieval_grader.GRADER_SYSTEM,
        "evaluaizer": evaluaizer_prompts.SYSTEM,
    }
    found.update({f"quizzer.{name}": value for name, value in vars(quizzer_prompts).items() if name.endswith("_SYSTEM") and isinstance(value, str)})
    return found


@pytest.mark.parametrize("name,prompt", system_prompts().items())
def test_prompt_memakai_format_baku(name, prompt):
    assert prompt.startswith("# ROLE\n")
    for section in SECTIONS:
        assert section in prompt, f"{name} tanpa {section}"


@pytest.mark.parametrize("name,prompt", system_prompts().items())
def test_prompt_tidak_menyebut_nama_dokumen_proyek(name, prompt):
    assert not DOCUMENT_NAMES.search(prompt), f"{name} menyebut nama dokumen"


@pytest.mark.parametrize("prompt", [agent.SYSTEM_PROMPT, scope_gate.CLASSIFIER_SYSTEM, retrieval_grader.GRADER_SYSTEM])
def test_prompt_klasifikasi_dan_agen_punya_contoh(prompt):
    assert "# EXAMPLES" in prompt


def all_system_prompts() -> dict[str, str]:
    found = dict(system_prompts())
    found.update({
        "annoter.table": annoter_prompts.table_system(),
        "annoter.classifier": annoter_prompts.image_classifier_system(),
        "annoter.arbiter": annoter_prompts.image_arbiter_system(),
        "common.image": image_prompts.image_system(),
        "common.formula": formula.SYSTEM,
        "common.formula_koordinat": formula.COORDINATE_SYSTEM,
    })
    found.update({f"common.image.{kind}": image_prompts.image_kind_system(kind) for kind in image_prompts.KIND_RULES})
    return found


@pytest.mark.parametrize("name,prompt", all_system_prompts().items())
def test_semua_prompt_sistem_memuat_aturan_anti_injeksi(name, prompt):
    assert all(rule in prompt for rule in guardrails.UNTRUSTED_RULES), name
