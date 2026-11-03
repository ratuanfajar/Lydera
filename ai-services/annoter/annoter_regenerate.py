from dataclasses import dataclass, field
from pathlib import Path

from annoter import config as annoter_config
from annoter import prompts, table
from common import config, llm, math_text
from common.formula import formula_input, formula_system, needs_coordinate_rules
from common.formula_check import spoken_issues
from common.speakable import description_issues, manual_reading_issues, speakable

IMAGE_CONTEXT_CHARS = annoter_config.CLASSIFY_CONTEXT_CHARS


@dataclass
class Regenerated:
    text: str
    ringkasan: str | None = None
    tabel: dict | None = None
    issues: list[str] = field(default_factory=list)


def regenerate(block_type: str, feedback: str, *, source_markup: str = "",
               image_path: Path | None = None, caption: str = "", context: str = "") -> Regenerated:
    """Hasilkan ulang bacaan satu blok berdasar feedback guru; dipanggil backend."""
    if block_type == "formula":
        spoken = llm.complete_text(
            formula_system(feedback=True, coordinate=needs_coordinate_rules(source_markup)),
            formula_input(source_markup, feedback),
            effort=config.TEXT_EFFORT,
        )
        return Regenerated(spoken, issues=spoken_issues(source_markup, spoken))
    if block_type == "table":
        data = table.request(
            prompts.table_system(feedback=True), prompts.table_input(caption, source_markup, feedback),
            _require_image(image_path),
        )
        result = table.from_response(data, source_markup, compare_ocr=False)
        return Regenerated(result.text, result.ringkasan, result.tabel, result.issues)
    if block_type == "image":
        described = speakable(llm.complete_vision(
            prompts.image_system(feedback=True), prompts.image_input(caption, context, feedback),
            _require_image(image_path),
        ))
        return Regenerated(described, issues=description_issues(described))
    raise ValueError(f"regenerasi tidak berlaku untuk block_type={block_type}")


def _require_image(image_path: Path | None) -> Path:
    if image_path is None or not Path(image_path).exists():
        raise FileNotFoundError(f"gambar tidak ditemukan: {image_path}")
    return Path(image_path)


@dataclass
class Edited:
    text: str
    source_markup: str | None = None
    ringkasan: str | None = None
    tabel: dict | None = None
    issues: list[str] = field(default_factory=list)


def edit(block_type: str, *, readable_text: str | None = None, source_markup: str | None = None, tabel: dict | None = None) -> Edited:
    """Turunkan bacaan blok khusus dari editan guru; `readable_text` yang dikirim dipakai apa adanya. ValueError bila masukan tidak valid."""
    if block_type not in ("formula", "table", "image"):
        raise ValueError(f"edit langsung tidak berlaku untuk block_type={block_type}")
    if readable_text is not None:
        problems = manual_reading_issues(readable_text)
        if problems:
            raise ValueError(" ".join(problems))
        return _with_manual_text(block_type, readable_text.strip(), source_markup, tabel)
    derived = _derived(block_type, source_markup, tabel)
    if derived is None:
        raise ValueError(_missing_message(block_type))
    return derived


def _missing_message(block_type: str) -> str:
    return {"formula": "kirim source_markup atau readable_text", "table": "kirim tabel atau readable_text"}.get(
        block_type, "kirim readable_text",
    )


def _with_manual_text(block_type: str, text: str, source_markup: str | None, tabel: dict | None) -> Edited:
    if block_type == "formula" and source_markup and source_markup.strip():
        _require_valid_latex(source_markup)
        return Edited(text, source_markup)
    if block_type == "table" and tabel is not None:
        structure = _edit_table(tabel)
        return Edited(text, structure.source_markup, structure.ringkasan, structure.tabel)
    if block_type == "table":
        return Edited(text, issues=["Bacaan tabel diganti tanpa tabel baru; ringkasan dan mode telusur sel masih dari tabel lama."])
    return Edited(text)


def _derived(block_type: str, source_markup: str | None, tabel: dict | None) -> Edited | None:
    if block_type == "formula" and source_markup and source_markup.strip():
        return _edit_formula(source_markup)
    if block_type == "table" and tabel is not None:
        return _edit_table(tabel)
    return None


def _wrapped(source_markup: str) -> str:
    return source_markup if "$" in source_markup else f"${source_markup.strip()}$"


def _require_valid_latex(source_markup: str) -> None:
    problems = math_text.latex_issues(_wrapped(source_markup))
    if problems:
        raise ValueError(" ".join(problems))


def _edit_formula(source_markup: str) -> Edited:
    _require_valid_latex(source_markup)
    issues: list[str] = []
    return Edited(math_text.readable_texts([_wrapped(source_markup)], issues)[0], source_markup, issues=issues)


def _edit_table(tabel: dict) -> Edited:
    problems = math_text.table_issues(tabel)
    if problems:
        raise ValueError(" ".join(problems))
    plain = math_text.plain_text_issues([tabel.get("judul") or "", *tabel["kolom"], *(cell for row in tabel["baris"] for cell in row)])
    if plain:
        raise ValueError(" ".join(plain))
    html = math_text.table_html(tabel)
    result = table.from_response({"deskripsi": "", "topik": "", "pengamatan": tabel}, html, compare_ocr=False)
    if result.tabel is None:
        raise ValueError(" ".join(result.issues))
    return Edited(result.text, html, result.ringkasan, result.tabel, result.issues)
