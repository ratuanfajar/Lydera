from dataclasses import dataclass, field
from pathlib import Path

from annoter import config as annoter_config
from annoter import prompts, table
from annoter.speakable import description_issues, speakable
from common import config, llm
from common.formula import formula_input, formula_system, needs_coordinate_rules
from common.formula_check import spoken_issues

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
