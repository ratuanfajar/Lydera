import json
from typing import Callable

from common import math_text
from quizzer import config
from quizzer.stimulus.base import Narration, StimulusKind
from quizzer.stimulus.text import latex_text_issues, shape_issues

NAME = "campuran"
MAX_COMPONENTS = 12
TEXT = "teks"
TABLE = "tabel"
PAYLOAD_KEYS = {TEXT: "teks", TABLE: "tabel"}

PROMPT_SCHEMA = (
    'jenis "campuran": {"komponen": [{"jenis": "teks", "teks": "..."} | {"jenis": "tabel", "tabel": {"judul": "...", '
    '"kolom": ["..."], "baris": [["..."]]}} | {"jenis": "gambar", "spesifikasi": {"svg": "..."}}]}. '
    "Komponen dibaca berurutan; semua data untuk menjawab harus ada pada komponen."
)


def _payload_key(name) -> str:
    return PAYLOAD_KEYS.get(name, "spesifikasi")


def build(kinds: dict[str, StimulusKind], active: Callable[[], list[str]]) -> StimulusKind:
    def validate(spec: dict) -> list[str]:
        components = spec.get("komponen")
        if not isinstance(components, list) or not 1 <= len(components) <= MAX_COMPONENTS:
            return [f"komponen harus berisi 1 sampai {MAX_COMPONENTS} komponen."]
        if len(json.dumps(spec, ensure_ascii=False)) > config.STIMULUS_MAX_CHARS:
            return ["spesifikasi terlalu besar."]
        usable = [name for name in active() if name != NAME]
        for index, component in enumerate(components, start=1):
            issues = _component_issues(component, kinds, usable)
            if issues:
                return [f"Komponen {index}: {issue}" for issue in issues]
        return []

    def finalize(spec: dict) -> dict:
        components = []
        for component in spec["komponen"]:
            name, key = component["jenis"], _payload_key(component["jenis"])
            payload = kinds[name].finalize(component[key]) if name in kinds else component[key]
            components.append({"jenis": name, key: payload})
        return {"komponen": components}

    def describe(spec: dict, context: str, issues: list[str]) -> dict:
        components = []
        for component in spec["komponen"]:
            name, key = component["jenis"], _payload_key(component["jenis"])
            kind = kinds.get(name)
            if kind is not None and kind.describe is not None:
                component = {"jenis": name, key: kind.describe(_without_derived(kind, component[key]), context, issues)}
            components.append(component)
        return {"komponen": components}

    def narrate(spec: dict) -> Narration:
        narrations = [_component_narration(component, kinds) for component in spec["komponen"]]
        first_table = next((item for item in narrations if item.tabel), None)
        text = " ".join(_sentence(item.readable_text) for item in narrations if item.readable_text)
        return Narration(text, first_table.tabel if first_table else None, first_table.ringkasan if first_table else None)

    return StimulusKind(NAME, 1, PROMPT_SCHEMA, ("komponen",), validate, narrate, finalize, raw_keys=("komponen",), describe=describe)


def _without_derived(kind: StimulusKind, payload: dict) -> dict:
    return {key: value for key, value in payload.items() if key not in kind.derived_keys}


def _sentence(text: str) -> str:
    stripped = text.strip()
    return stripped if stripped.endswith((".", "!", "?")) else f"{stripped}."


def _component_issues(component, kinds: dict[str, StimulusKind], usable: list[str]) -> list[str]:
    if not isinstance(component, dict):
        return ["komponen harus berupa objek."]
    name = component.get("jenis")
    if set(component) != {"jenis", _payload_key(name)}:
        return [f"komponen jenis '{name}' harus memuat tepat kunci jenis dan {_payload_key(name)}."]
    payload = component[_payload_key(name)]
    if name == TEXT:
        return latex_text_issues(payload)
    if name not in kinds or name not in usable:
        return [f"jenis '{name}' tidak tersedia."]
    if not isinstance(payload, dict):
        return ["isi komponen harus berupa objek."]
    kind = kinds[name]
    issues = shape_issues({key: value for key, value in payload.items() if key not in kind.raw_keys})
    if issues:
        return issues
    unknown = sorted(set(payload) - set(kind.keys) - set(kind.derived_keys))
    if unknown:
        return [f"memuat kunci yang tidak dikenal: {', '.join(unknown)}."]
    return kind.validate(payload)


def _component_narration(component: dict, kinds: dict[str, StimulusKind]) -> Narration:
    name = component["jenis"]
    if name == TEXT:
        return Narration(math_text.readable_texts([component["teks"].strip()])[0])
    return kinds[name].narrate(component[_payload_key(name)])
