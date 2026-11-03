import copy
import re

from common import math_text
from quizzer import config
from quizzer.stimulus import campuran, gambar, tabel
from quizzer.stimulus.base import StimulusKind
from quizzer.stimulus.text import latex_text_issues, shape_issues

TEXT = "teks"
ALL_TYPES = "*"
NARRATION_VISUAL = re.compile(r"\b(foto|ilustrasi|sketsa)\b", re.IGNORECASE)
ALWAYS_ALLOWED_KEYS = ("skema_versi",)
KINDS: dict[str, StimulusKind] = {
    kind.name: kind
    for kind in (tabel.KIND, gambar.KIND)
}


def typed_names() -> list[str]:
    names = list(KINDS) if ALL_TYPES in config.STIMULUS_TYPES else [name for name in config.STIMULUS_TYPES if name in KINDS]
    return [name for name in names if KINDS[name].available()]


KINDS[campuran.NAME] = campuran.build(KINDS, typed_names)


def is_typed(stimulus) -> bool:
    return isinstance(stimulus, dict) and stimulus.get("jenis") not in (None, TEXT)


def prompt_schemas() -> str:
    return "\n".join(KINDS[name].prompt_schema for name in typed_names())


def editable_spec(name: str, spec: dict) -> dict:
    kept = {key: value for key, value in spec.items() if key in KINDS[name].keys}
    if name == campuran.NAME:
        kept["komponen"] = [_editable_component(component) for component in kept.get("komponen") or []]
    return kept


def current_narasi(stimulus: dict) -> str | None:
    """Narasi pengantar stimulus bertipe yang tersimpan (sumber bila ada rumus, selain itu bacaan di depan narasi jenisnya); None bila tidak bisa dipulihkan."""
    kind = KINDS.get(stimulus.get("jenis"))
    spec = stimulus.get("spesifikasi")
    if kind is None or not isinstance(spec, dict):
        return None
    readable = str(stimulus.get("readable_text") or "").strip()
    try:
        narration = kind.narrate({key: value for key, value in spec.items() if key != "skema_versi"}).readable_text
    except Exception:
        return None
    if not narration or not readable.endswith(narration):
        return None
    return str(stimulus.get("source_markup") or "") or readable[: -len(narration)].strip()


def _editable_component(component):
    if not isinstance(component, dict):
        return component
    inner = component.get("spesifikasi")
    if component.get("jenis") in KINDS and isinstance(inner, dict):
        return {**component, "spesifikasi": editable_spec(component["jenis"], inner)}
    return component


def check(stimulus: dict) -> list[str]:
    name = stimulus.get("jenis")
    if name not in typed_names():
        return [f"Jenis stimulus '{name}' tidak tersedia."]
    spec = stimulus.get("spesifikasi")
    kind = KINDS[name]
    scanned = {key: value for key, value in spec.items() if key not in kind.raw_keys} if isinstance(spec, dict) else spec
    narasi = str(stimulus.get("narasi") or "")
    issues = (latex_text_issues(narasi) if narasi.strip() else []) or shape_issues(scanned)
    if issues:
        return issues
    if NARRATION_VISUAL.search(str(stimulus.get("narasi") or "")):
        return ["Narasi tidak boleh merujuk foto, ilustrasi, atau sketsa."]
    unknown = sorted(set(spec) - set(kind.keys) - set(kind.derived_keys) - set(ALWAYS_ALLOWED_KEYS))
    if unknown:
        return [f"Spesifikasi memuat kunci yang tidak dikenal: {', '.join(unknown)}."]
    try:
        return kind.validate(spec)
    except (AttributeError, TypeError, KeyError, IndexError, ValueError, ZeroDivisionError):
        return [f"Bentuk spesifikasi tidak sesuai skema jenis {name}."]


def derive(stimulus: dict, issues: list[str] | None = None) -> dict:
    """Turunkan teks siap-baca stimulus bertipe dari spesifikasinya; spesifikasi harus sudah lolos `check`."""
    kind = KINDS[stimulus["jenis"]]
    intro = str(stimulus.get("narasi") or "").strip()
    spec = copy.deepcopy({k: v for k, v in stimulus["spesifikasi"].items() if k != "skema_versi" and k not in kind.derived_keys})
    if kind.describe is not None:
        spec = kind.describe(spec, intro, issues if issues is not None else [])
    spec = kind.finalize(spec)
    narration = kind.narrate(spec)
    spoken_intro = math_text.readable_texts([intro], issues)[0] if intro else ""
    return {
        "jenis": kind.name,
        "spesifikasi": {**spec, "skema_versi": kind.schema_version},
        "readable_text": " ".join(part for part in (spoken_intro, narration.readable_text) if part),
        "source_markup": intro if "$" in intro else "",
        "ringkasan": narration.ringkasan,
        "tabel": narration.tabel,
    }
