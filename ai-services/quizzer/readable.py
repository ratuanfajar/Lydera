from dataclasses import dataclass

from common import math_text
from quizzer.checks import LABELS
from quizzer.stimulus import registry


def derive_fields(markup: dict, issues: list[str] | None = None) -> tuple[dict, dict | None]:
    """Turunkan teks siap-baca dari markup {question, options, langkah, kesimpulan}; markup jadi None bila tanpa rumus."""
    options = {label: markup["options"][label] for label in LABELS}
    flat = [markup["question"], *options.values(), *markup["langkah"], markup["kesimpulan"]]
    if not any("$" in text for text in flat):
        return markup, None
    spoken = math_text.readable_texts(flat, issues)
    count = len(options)
    readable = {
        "question": spoken[0],
        "options": dict(zip(options, spoken[1:1 + count])),
        "langkah": spoken[1 + count:-1],
        "kesimpulan": spoken[-1],
    }
    return readable, markup


@dataclass
class StimulusReading:
    readable_text: str
    source_markup: str | None = None
    ringkasan: str | None = None
    tabel: dict | None = None


def derive_stimulus(markup: str, issues: list[str] | None = None) -> StimulusReading:
    """Turunkan bacaan stimulus dari markup berisi $...$ dan tabel HTML opsional; source_markup None bila tanpa keduanya."""
    text, table = math_text.split_table(markup)
    if "<table" in markup.lower() and table is None:
        raise ValueError("tabel HTML pada stimulus tidak valid")
    if "$" not in text and table is None:
        return StimulusReading(text)
    readable = math_text.readable_texts([text], issues)[0]
    if table is None:
        return StimulusReading(readable, markup)
    spoken = math_text.spoken_table(table, issues)
    readable = f"{readable} {math_text.table_readable(spoken)}".strip()
    return StimulusReading(readable, markup, math_text.table_summary(spoken), spoken)


def stimulus_markup(stimulus: dict) -> str:
    text = str(stimulus.get("readable_text", "")).strip()
    table = stimulus.get("tabel")
    return f"{text}\n\n{math_text.table_html(table)}" if table else text


def derive(data: dict) -> tuple[dict, list[str]]:
    """Ubah keluaran generator (teks berisi markup) menjadi data siap simpan beserta temuan bacaan rumus."""
    markup = {
        "question": data["question_text"], "options": dict(data["options"]),
        "langkah": list(data["langkah"]), "kesimpulan": data["kesimpulan"],
    }
    issues: list[str] = []
    readable, soal_markup = derive_fields(markup, issues)
    data = {**data, "question_text": readable["question"], "options": readable["options"],
            "langkah": readable["langkah"], "kesimpulan": readable["kesimpulan"], "markup": soal_markup}
    stimulus = data.get("stimulus")
    if registry.is_typed(stimulus):
        data["stimulus"] = registry.derive(stimulus, issues)
    elif isinstance(stimulus, dict):
        source = stimulus_markup(stimulus)
        reading = derive_stimulus(source, issues)
        data["stimulus"] = {
            "readable_text": reading.readable_text, "source_markup": reading.source_markup or "",
            "ringkasan": reading.ringkasan, "tabel": reading.tabel,
        }
    return data, list(dict.fromkeys(issues))


def typed_stimulus_issues(data: dict) -> list[str]:
    """Periksa spesifikasi stimulus bertipe pada keluaran generator; kosong bila stimulus teks atau null."""
    stimulus = data.get("stimulus")
    return registry.check(stimulus) if registry.is_typed(stimulus) else []


def markup_issues(data: dict) -> list[str]:
    """Periksa LaTeX inline dan tabel pada keluaran generator sebelum diturunkan menjadi teks siap-baca."""
    texts = [data["question_text"], data["kesimpulan"], *data["options"].values(), *data["langkah"]]
    stimulus = data.get("stimulus")
    issues = []
    if isinstance(stimulus, dict):
        texts.append(str(stimulus.get("readable_text", "")))
        texts.append(str(stimulus.get("narasi", "")))
        if stimulus.get("tabel") is not None:
            issues.extend(math_text.table_issues(stimulus["tabel"]))
            if not issues:
                texts.extend(str(cell) for cell in [*stimulus["tabel"]["kolom"], *(c for row in stimulus["tabel"]["baris"] for c in row)])
    for text in texts:
        issues.extend(math_text.latex_issues(str(text)))
    return list(dict.fromkeys(issues))


def fields_issues(markup: dict) -> list[str]:
    return markup_issues({
        "question_text": markup["question"], "kesimpulan": markup["kesimpulan"],
        "options": markup["options"], "langkah": markup["langkah"],
    })
