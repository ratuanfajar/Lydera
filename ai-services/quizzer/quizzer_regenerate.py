import logging

from quizzer import checks, readable, revise, validate
from quizzer import segment as segment_module
from quizzer.stimulus import registry
from common import math_text, svg_raster
from common.parallel import parallel_map

logger = logging.getLogger(__name__)


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
    structure = checks.structure_issues(data)
    if structure:
        return structure
    issues = checks.code_issues(data)
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


def _revised_text_stimulus(source_text: str, stimulus_markup: str, feedback: str) -> tuple[dict, str, list[str]]:
    new_markup = revise.revise_stimulus(source_text, stimulus_markup, feedback)
    flags = math_text.latex_issues(new_markup)
    reading = readable.derive_stimulus(new_markup, flags)
    stimulus = {
        "readable_text": reading.readable_text, "source_markup": reading.source_markup or "",
        "ringkasan": reading.ringkasan, "tabel": reading.tabel,
    }
    return stimulus, new_markup, flags


def _revised_typed_stimulus(source_text: str, stimulus_readable: str, jenis: str, spec: dict, feedback: str) -> tuple[dict, str, list[str]]:
    if jenis not in registry.typed_names():
        raise ValueError(f"revisi stimulus tidak valid: jenis '{jenis}' tidak tersedia.")
    revised = revise.revise_stimulus_typed(source_text, stimulus_readable, jenis, registry.editable_spec(jenis, spec), feedback)
    issues = registry.check(revised)
    if issues:
        raise ValueError("revisi stimulus tidak valid: " + "; ".join(issues))
    flags = math_text.latex_issues(revised["narasi"])
    stimulus = registry.derive(revised, flags)
    return stimulus, stimulus["readable_text"], flags


def compute_regeneration(all_blocks, source_start, source_end, stimulus_source_markup: str, stimulus_readable: str,
                          target_soal: dict, sibling_soal: list[dict], feedback: str,
                          stimulus_jenis: str | None = None, stimulus_spec: dict | None = None) -> dict:
    source_text = segment_module.span_text(all_blocks, source_start, source_end)
    typed = bool(stimulus_jenis) and stimulus_jenis != registry.TEXT and isinstance(stimulus_spec, dict)
    stimulus_markup = stimulus_readable if typed else stimulus_source_markup or stimulus_readable
    stimulus = {"readable_text": stimulus_readable, "source_markup": stimulus_source_markup}
    if typed:
        stimulus = {**stimulus, "jenis": stimulus_jenis, "spesifikasi": stimulus_spec}

    edit = revise.revise_soal(source_text, stimulus_markup, target_soal, feedback)
    if not edit.get("needs_stimulus_change"):
        if _soal_content_equal(target_soal, edit):
            return {"new_stimulus": None, "soal_updates": []}
        data, issues = _finalize(source_text, edit, stimulus)
        return {"new_stimulus": None, "soal_updates": [(target_soal["id"], data, issues)]}

    if typed:
        new_stimulus, new_markup, stimulus_flags = _revised_typed_stimulus(source_text, stimulus_readable, stimulus_jenis, stimulus_spec, feedback)
    else:
        new_stimulus, new_markup, stimulus_flags = _revised_text_stimulus(source_text, stimulus_markup, feedback)
    all_soal = [target_soal] + sibling_soal
    rechecked = parallel_map(lambda s: revise.recheck_soal_for_new_stimulus(source_text, new_markup, s), all_soal)
    changed = [(s, raw) for s, raw in zip(all_soal, rechecked) if not _soal_content_equal(s, raw)]
    finalized = parallel_map(lambda pair: _finalize(source_text, pair[1], new_stimulus), changed)
    stimulus_flags = list(dict.fromkeys(stimulus_flags))
    updates = [(s["id"], data, [*stimulus_flags, *issues]) for (s, _), (data, issues) in zip(changed, finalized)]
    return {"new_stimulus": new_stimulus, "soal_updates": updates}


def _table_strings(table) -> list[str]:
    if not isinstance(table, dict):
        return []
    return [table.get("judul") or "", *table.get("kolom", []), *(cell for row in table.get("baris", []) for cell in row)]


def _spec_strings(jenis: str, spec: dict) -> list[str]:
    if jenis == "tabel":
        return _table_strings(spec)
    if jenis != "campuran":
        return []
    strings: list[str] = []
    for part in spec.get("komponen", []):
        strings.extend([part.get("teks") or ""] if part.get("jenis") == "teks" else _table_strings(part.get("tabel")))
    return strings


def _typed_stimulus_edit(stimulus: dict, edit: dict) -> tuple[dict, list[str]]:
    flags: list[str] = []
    narasi = edit.get("narasi")
    if narasi is None:
        narasi = registry.current_narasi(stimulus)
        if narasi is None:
            narasi = ""
            flags.append("Narasi pengantar lama tidak dapat dipulihkan dan tidak ikut; kirim narasi bila masih diperlukan.")
    raw = {"jenis": stimulus["jenis"], "narasi": narasi, "spesifikasi": edit["spesifikasi"]}
    problems = registry.check(raw) or math_text.plain_text_issues([narasi, *_spec_strings(stimulus["jenis"], edit["spesifikasi"])])
    if problems:
        raise ValueError("stimulus tidak valid: " + "; ".join(problems))
    flags.extend(math_text.latex_issues(narasi))
    try:
        return registry.derive(raw, flags), flags
    except svg_raster.RenderError as exc:
        raise ValueError(f"Gambar tidak dapat dirender: {exc}") from exc


def _text_stimulus_edit(edit: dict) -> tuple[dict, list[str]]:
    markup = str(edit.get("source_markup") or "").strip()
    if not markup:
        raise ValueError("stimulus tidak valid: source_markup tidak boleh kosong")
    problems = math_text.latex_issues(markup)
    if problems:
        raise ValueError("stimulus tidak valid: " + "; ".join(problems))
    text, table = math_text.split_table(markup)
    problems = math_text.plain_text_issues([text, *_table_strings(table)])
    if problems:
        raise ValueError("stimulus tidak valid: " + " ".join(problems))
    flags: list[str] = []
    reading = readable.derive_stimulus(markup, flags)
    return {
        "readable_text": reading.readable_text, "source_markup": reading.source_markup or "",
        "ringkasan": reading.ringkasan, "tabel": reading.tabel,
    }, flags


def compute_stimulus_edit(all_blocks, source_start, source_end, stimulus: dict, soal_list: list[dict], edit: dict) -> dict:
    """Turunkan ulang stimulus dari editan guru lalu verifikasi ulang semua soal di cluster; ValueError bila editan tidak valid."""
    typed = bool(stimulus.get("jenis")) and stimulus["jenis"] != registry.TEXT and isinstance(stimulus.get("spesifikasi"), dict)
    new_stimulus, flags = _typed_stimulus_edit(stimulus, edit) if typed else _text_stimulus_edit(edit)
    source_text = segment_module.span_text(all_blocks, source_start, source_end)

    def review(soal: dict) -> tuple[int, list[str]]:
        try:
            issues = review_soal(source_text, {**soal, "stimulus": new_stimulus}, new_stimulus["readable_text"])
        except Exception:
            logger.exception("verifikasi ulang soal %s setelah edit stimulus gagal", soal["id"])
            issues = ["Verifikasi otomatis gagal dijalankan; periksa soal ini secara manual."]
        return soal["id"], list(dict.fromkeys([*flags, *issues]))

    return {"new_stimulus": new_stimulus, "soal_issues": dict(parallel_map(review, soal_list))}
