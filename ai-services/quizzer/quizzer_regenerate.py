from quizzer import checks, readable, revise, validate
from quizzer import segment as segment_module
from common import math_text
from common.parallel import parallel_map


def _soal_content_equal(original: dict, data: dict) -> bool:
    return (
        original["question_text"] == data["question_text"]
        and original["options"] == data["options"]
        and original["correct_option"] == data["correct_option"]
        and original["langkah"] == data["langkah"]
        and original["kesimpulan"] == data["kesimpulan"]
    )


def review_soal(source_text: str, data: dict, stimulus_text: str = "") -> list[str]:
    """Pemeriksaan kode dan verifikasi validator untuk satu soal; mengembalikan daftar masalah (kosong bila lolos)."""
    issues = checks.code_issues(data)
    if checks.structure_issues(data):
        return issues
    verification = validate.verify_soal(source_text, data, stimulus_text)
    return issues + verification["issues"] + verification["unavailable"]


def _finalize(source_text: str, raw: dict, stimulus: dict) -> tuple[dict, list[str]]:
    structure = checks.structure_issues(raw)
    if structure:
        raise ValueError("revisi tidak valid: " + "; ".join(structure))
    markup_problems = readable.markup_issues(raw)
    derived, spoken_flags = readable.derive(raw)
    data = {**derived, "stimulus": stimulus}
    return data, markup_problems + spoken_flags + review_soal(source_text, data, stimulus["readable_text"])


def compute_regeneration(all_blocks, source_start, source_end, stimulus_source_markup: str, stimulus_readable: str,
                          target_soal: dict, sibling_soal: list[dict], feedback: str) -> dict:
    source_text = segment_module.span_text(all_blocks, source_start, source_end)
    stimulus_markup = stimulus_source_markup or stimulus_readable
    stimulus = {"readable_text": stimulus_readable, "source_markup": stimulus_source_markup}

    edit = revise.revise_soal(source_text, stimulus_markup, target_soal, feedback)
    if not edit.get("needs_stimulus_change"):
        if _soal_content_equal(target_soal, edit):
            return {"new_stimulus": None, "soal_updates": []}
        data, issues = _finalize(source_text, edit, stimulus)
        return {"new_stimulus": None, "soal_updates": [(target_soal["id"], data, issues)]}

    new_markup = revise.revise_stimulus(source_text, stimulus_markup, feedback)
    stimulus_flags = math_text.latex_issues(new_markup)
    reading = readable.derive_stimulus(new_markup, stimulus_flags)
    new_stimulus = {
        "readable_text": reading.readable_text, "source_markup": reading.source_markup or "",
        "ringkasan": reading.ringkasan, "tabel": reading.tabel,
    }
    all_soal = [target_soal] + sibling_soal
    rechecked = parallel_map(lambda s: revise.recheck_soal_for_new_stimulus(source_text, new_markup, s), all_soal)
    changed = [(s, raw) for s, raw in zip(all_soal, rechecked) if not _soal_content_equal(s, raw)]
    finalized = parallel_map(lambda pair: _finalize(source_text, pair[1], new_stimulus), changed)
    stimulus_flags = list(dict.fromkeys(stimulus_flags))
    updates = [(s["id"], data, [*stimulus_flags, *issues]) for (s, _), (data, issues) in zip(changed, finalized)]
    return {"new_stimulus": new_stimulus, "soal_updates": updates}
