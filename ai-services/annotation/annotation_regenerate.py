from pathlib import Path

import formula
import image
import llm
import table

FEEDBACK_TEMPLATE = "Koreksi dari guru: {feedback}\nPerbaiki bacaan sesuai koreksi ini."


def regenerate(block_type: str, feedback: str, *, source_markup: str = "",
               image_path: Path | None = None, caption: str = "", context: str = "") -> str:
    """Hasilkan ulang bacaan satu blok berdasar feedback guru; dipanggil backend."""
    note = FEEDBACK_TEMPLATE.format(feedback=feedback.strip())
    if block_type == "formula":
        return llm.complete_text(formula.SYSTEM, f"{source_markup}\n\n{note}")
    if block_type == "table":
        user = f"{table.build_prompt(caption, source_markup)}\n\n{note}"
        return llm.complete_vision(table.SYSTEM, user, _require_image(image_path))
    if block_type == "image":
        user = f"{image.build_prompt(caption, context)}\n\n{note}"
        return llm.complete_vision(image.SYSTEM, user, _require_image(image_path))
    raise ValueError(f"regenerasi tidak berlaku untuk block_type={block_type}")


def _require_image(image_path: Path | None) -> Path:
    if image_path is None or not Path(image_path).exists():
        raise FileNotFoundError(f"gambar tidak ditemukan: {image_path}")
    return Path(image_path)
