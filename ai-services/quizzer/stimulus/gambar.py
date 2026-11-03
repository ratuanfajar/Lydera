import hashlib
import re
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

from common import config as common_config
from common import svg_raster
from common.image_describe import describe_cached
from common.image_prompts import image_input, image_system
from common.speakable import description_issues, speakable
from quizzer import config
from quizzer.stimulus.base import Narration, StimulusKind

SVG_NS = "http://www.w3.org/2000/svg"
ELEMENTS = ("svg", "g", "defs", "marker", "rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "text", "tspan", "title", "desc")
TEXT_ELEMENTS = ("text", "tspan", "title", "desc")
NUMERIC_ATTRIBUTES = (
    "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "dx", "dy", "width", "height", "stroke-width", "font-size",
    "markerWidth", "markerHeight", "refX", "refY",
)
OPACITY_ATTRIBUTES = ("opacity", "fill-opacity", "stroke-opacity")
COLOR_ATTRIBUTES = ("fill", "stroke")
MARKER_ATTRIBUTES = ("marker-start", "marker-end")
ENUMERATIONS = {
    "stroke-linecap": ("butt", "round", "square"),
    "stroke-linejoin": ("miter", "round", "bevel"),
    "text-anchor": ("start", "middle", "end"),
    "dominant-baseline": ("auto", "middle", "central", "hanging", "alphabetic", "text-before-edge", "text-after-edge"),
    "font-weight": ("normal", "bold", "100", "200", "300", "400", "500", "600", "700", "800", "900"),
    "markerUnits": ("strokeWidth", "userSpaceOnUse"),
    "preserveAspectRatio": ("none", "xMidYMid", "xMinYMin", "xMidYMid meet", "xMidYMid slice"),
}
OTHER_ATTRIBUTES = ("id", "points", "d", "transform", "viewBox", "stroke-dasharray", "orient")
ATTRIBUTES = (*NUMERIC_ATTRIBUTES, *OPACITY_ATTRIBUTES, *COLOR_ATTRIBUTES, *MARKER_ATTRIBUTES, *ENUMERATIONS, *OTHER_ATTRIBUTES)
FORBIDDEN_MARKUP = ("<!", "<?")
NUMBER = r"[+-]?\d+(?:\.\d+)?"
NUMERIC_VALUE = re.compile(rf"^{NUMBER}(?:px|em|%)?$")
OPACITY_VALUE = re.compile(r"^(?:0(?:\.\d+)?|1(?:\.0+)?)$")
COLOR_VALUE = re.compile(r"^(?:none|currentColor|#[0-9a-fA-F]{3,8}|[a-zA-Z]{3,20})$")
MARKER_VALUE = re.compile(r"^url\(#([A-Za-z][A-Za-z0-9_-]{0,40})\)$")
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,40}$")
PATH_DATA = re.compile(rf"^(?:[MmLlHhVvCcSsQqTtAaZz]|{NUMBER}|[\s,])+$")
POINTS_DATA = re.compile(rf"^(?:{NUMBER}|[\s,])+$")
TRANSFORM = re.compile(rf"^(?:\s*(?:translate|scale|rotate|skewX|skewY|matrix)\(\s*{NUMBER}(?:[\s,]+{NUMBER})*\s*\)\s*)+$")
ORIENT = re.compile(rf"^(?:auto|auto-start-reverse|{NUMBER})$")
NUMBERS = re.compile(NUMBER)
LABEL_NUMBER = re.compile(r"-?\d+(?:[.,]\d+)*", re.ASCII)
WORD_FREE_MARKS = re.compile(r"[-\d.,;:()\[\]{}=+*/<>!?%\s]+")
MAX_COORDINATE = 10000
MAX_TEXT_CHARS = 200
MIN_DASH = 0.5
NESTING_ALLOWANCE = 4
NEGATIVE_WORDS = ("negatif", "minus")

PROMPT_SCHEMA = (
    "jenis \"gambar\": gambar yang Anda buat untuk soal yang bergantung pada bentuk, posisi, atau pola yang lebih jelas bila "
    "digambar daripada diceritakan, misalnya grafik atau diagram data, sumbu koordinat dengan titik, garis, atau kurva, "
    "garis bilangan, bangun datar atau bangun ruang, dan diagram hubungan antar objek. Guru melihat gambar itu, siswa "
    "tunanetra mendengar deskripsinya. Bentuknya {\"svg\": \"<svg viewBox='0 0 lebar tinggi'>...</svg>\"}. Anda menulis SVG sendiri dalam satu baris "
    "dengan tanda kutip tunggal untuk atribut supaya JSON tetap valid, dan hanya boleh memakai elemen "
    f"{', '.join(ELEMENTS)}, tanpa style, skrip, tautan, atau gambar luar; atribut hanya presentasi dasar dan geometri. "
    "viewBox wajib. Jaga SVG ringkas (sekitar 60 elemen atau kurang). Teks di dalam gambar berupa teks biasa. Tulis semua "
    "label, nilai, dan tanda yang dibutuhkan soal langsung di dalam gambar: setiap besaran yang dipakai soal harus tampak "
    "jelas sebagai tanda dengan label, dan objek yang dinyatakan berada pada suatu bangun harus digambar tepat di bangun itu. Hubungan yang tidak tampak dari bentuk saja "
    "(misalnya kesamaan panjang, kesejajaran, atau sudut siku-siku) tidak ikut terbaca pada deskripsi dan tidak dibacakan "
    "dari elemen title atau desc, jadi tulis hubungan itu di \"narasi\". Teks bacaan untuk siswa tunanetra dibuat sistem "
    "dari gambar yang Anda tulis."
)
KEYS = ("svg",)
DERIVED_KEYS = ("deskripsi",)
CACHE_SOURCE = "stimulus-svg"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _foreign(tag: str) -> bool:
    return tag.startswith("{") and not tag.startswith(f"{{{SVG_NS}}}")


def _within_bounds(value: str) -> bool:
    return all(abs(float(number)) <= MAX_COORDINATE for number in NUMBERS.findall(value))


def _dash_ok(value: str) -> bool:
    parts = re.split(r"[\s,]+", value.strip())
    return len(parts) <= 8 and all(re.fullmatch(r"\d+(?:\.\d+)?", part) and MIN_DASH <= float(part) <= MAX_COORDINATE for part in parts)


def _viewbox_ok(value: str) -> bool:
    parts = re.split(r"[\s,]+", value.strip())
    if len(parts) != 4 or not all(re.fullmatch(NUMBER, part) for part in parts):
        return False
    numbers = [float(part) for part in parts]
    return numbers[2] > 0 and numbers[3] > 0 and all(abs(number) <= MAX_COORDINATE for number in numbers)


def _value_issue(name: str, value: str) -> str | None:
    if name in NUMERIC_ATTRIBUTES:
        return None if NUMERIC_VALUE.match(value) and _within_bounds(value) else "harus berupa bilangan wajar"
    if name in OPACITY_ATTRIBUTES:
        return None if OPACITY_VALUE.match(value) else "harus bilangan 0 sampai 1"
    if name in COLOR_ATTRIBUTES:
        return None if COLOR_VALUE.match(value) else "harus none, currentColor, kode warna heks, atau nama warna"
    if name in MARKER_ATTRIBUTES:
        return None if MARKER_VALUE.match(value) else "harus berupa url(#id) lokal"
    if name in ENUMERATIONS:
        return None if value in ENUMERATIONS[name] else f"harus salah satu dari {', '.join(ENUMERATIONS[name])}"
    checks = {
        "d": lambda: PATH_DATA.match(value) and _within_bounds(value),
        "points": lambda: POINTS_DATA.match(value) and _within_bounds(value),
        "transform": lambda: TRANSFORM.match(value) and _within_bounds(value),
        "id": lambda: IDENTIFIER.match(value),
        "orient": lambda: ORIENT.match(value) and _within_bounds(value),
        "stroke-dasharray": lambda: value == "none" or _dash_ok(value),
        "viewBox": lambda: _viewbox_ok(value),
    }
    return None if checks[name]() else "bernilai tidak valid"


def _attribute_issues(element: ET.Element, tag: str) -> list[str]:
    issues = []
    for name, value in element.attrib.items():
        if "{" in name or name not in ATTRIBUTES:
            issues.append(f"atribut '{_local(name)}' pada <{tag}> tidak diizinkan.")
            continue
        problem = _value_issue(name, value.strip())
        if problem:
            issues.append(f"atribut '{name}' pada <{tag}> {problem}.")
    return issues


def _hidden_text(element: ET.Element) -> bool:
    if _local(element.tag) not in ("text", "tspan"):
        return False
    return any(element.attrib.get(name, "").strip() in ("0", "0.0") for name in ("opacity", "fill-opacity", "font-size"))


def _collect_references(element: ET.Element, tag: str, state: dict) -> None:
    identifier = element.attrib.get("id")
    if identifier:
        if identifier in state["ids"]:
            state["issues"].append(f"id '{identifier}' dipakai lebih dari sekali.")
        state["ids"].add(identifier)
        if tag == "marker":
            state["markers"].add(identifier)
    for name in MARKER_ATTRIBUTES:
        match = MARKER_VALUE.match(element.attrib.get(name, "").strip())
        if match:
            state["references"].append(match.group(1))
            if state["inside_marker"]:
                state["issues"].append("marker tidak boleh merujuk marker lain.")


def _walk(element: ET.Element, depth: int, state: dict) -> None:
    tag = _local(element.tag)
    state["count"][0] += 1
    if _foreign(element.tag) or tag not in ELEMENTS:
        state["issues"].append(f"elemen <{tag}> tidak diizinkan.")
        return
    if state["count"][0] > config.SVG_MAX_ELEMENTS or depth > config.STIMULUS_MAX_DEPTH + NESTING_ALLOWANCE:
        state["issues"].append("SVG terlalu besar atau terlalu bersarang.")
        return
    state["issues"].extend(_attribute_issues(element, tag))
    _collect_references(element, tag, state)
    if _hidden_text(element):
        state["issues"].append("teks tidak boleh disembunyikan dengan opacity atau ukuran font nol.")
    if element.text and element.text.strip() and tag not in TEXT_ELEMENTS:
        state["issues"].append(f"<{tag}> tidak boleh berisi teks langsung; pakai <text>.")
    for child in element:
        if child.tail and child.tail.strip() and tag not in ("text", "tspan"):
            state["issues"].append(f"<{tag}> tidak boleh berisi teks langsung; pakai <text>.")
        _walk(child, depth + 1, {**state, "inside_marker": state["inside_marker"] or tag == "marker"})


def _parse(svg) -> tuple[ET.Element | None, list[str]]:
    if not isinstance(svg, str) or not svg.strip():
        return None, ["svg wajib berupa teks SVG tidak kosong."]
    if len(svg) > config.STIMULUS_MAX_SVG_CHARS:
        return None, [f"svg terlalu panjang (paling banyak {config.STIMULUS_MAX_SVG_CHARS} karakter)."]
    if any(token in svg.lower() for token in FORBIDDEN_MARKUP):
        return None, ["svg tidak boleh memuat DOCTYPE, ENTITY, komentar, instruksi pemrosesan, atau CDATA."]
    try:
        return ET.fromstring(svg.strip()), []
    except ET.ParseError:
        return None, ["svg bukan XML yang valid."]


def _label_texts(root: ET.Element) -> list[str]:
    return [" ".join("".join(element.itertext()).split()) for element in root.iter() if _local(element.tag) in ("text", "tspan")]


def _all_texts(root: ET.Element) -> list[str]:
    return [" ".join("".join(element.itertext()).split()) for element in root.iter() if _local(element.tag) in TEXT_ELEMENTS]


def _control_characters(texts: list[str]) -> bool:
    return any(unicodedata.category(char) in ("Cc", "Cf") and char not in "\t\n\r" for text in texts for char in text)


def _normalized(number: str) -> str:
    unsigned = number.lstrip("-")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", unsigned):
        unsigned = unsigned.replace(".", "")
    unsigned = unsigned.replace(".", ",")
    if "," in unsigned:
        unsigned = unsigned.rstrip("0").rstrip(",")
    return unsigned


def _label_words(text: str) -> str:
    return " ".join(WORD_FREE_MARKS.sub(" ", text).split())


def _has_word(lowered: str, word: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(word)}(?!\w)", lowered) is not None


def _unmentioned_labels(root: ET.Element, description: str) -> list[str]:
    lowered = description.lower()
    texts = {_label_words(text) for text in _label_texts(root)}
    return sorted(text for text in texts if text and not all(_has_word(lowered, word) for word in text.lower().split()))


def _missing_numbers(root: ET.Element, description: str) -> list[str]:
    labels = [token for text in _label_texts(root) for token in LABEL_NUMBER.findall(text)]
    spoken = {_normalized(token) for token in LABEL_NUMBER.findall(description)}
    return sorted({_normalized(token) for token in labels} - spoken - {"0", "1"})


def _omission_feedback(root: ET.Element, description: str) -> str:
    items = [*_missing_numbers(root, description), *_unmentioned_labels(root, description)]
    if not items:
        return ""
    return f"Deskripsi sebelumnya tidak menyebut hal berikut yang tertulis di gambar; sebutkan semuanya: {', '.join(items)}."


def _number_issues(root: ET.Element, description: str) -> list[str]:
    labels = [token for text in _label_texts(root) for token in LABEL_NUMBER.findall(text)]
    missing = _missing_numbers(root, description)
    issues = [f"angka di dalam gambar belum ada di deskripsi: {', '.join(missing)}."] if missing else []
    if any(token.startswith("-") for token in labels) and not any(word in description.lower() for word in NEGATIVE_WORDS):
        issues.append("label gambar memuat bilangan negatif; sebut 'negatif' di deskripsi.")
    unmentioned = _unmentioned_labels(root, description)
    if unmentioned:
        issues.append(f"label di dalam gambar belum disebut di deskripsi: {', '.join(unmentioned)}.")
    return issues


def _structure_issues(root: ET.Element) -> list[str]:
    state = {"count": [0], "issues": [], "ids": set(), "markers": set(), "references": [], "inside_marker": False}
    _walk(root, 1, state)
    found = state["issues"]
    if "viewBox" not in root.attrib:
        found.append("elemen <svg> wajib punya viewBox berisi empat bilangan dengan lebar dan tinggi lebih dari nol.")
    found.extend(f"marker '{name}' tidak ada." for name in dict.fromkeys(state["references"]) if name not in state["markers"])
    texts = _all_texts(root)
    if any(len(text) > MAX_TEXT_CHARS for text in texts):
        found.append(f"teks di dalam gambar paling banyak {MAX_TEXT_CHARS} karakter per label.")
    if _control_characters(texts):
        found.append("teks di dalam gambar tidak boleh memuat karakter kontrol.")
    if not any(_local(element.tag) not in ("svg", "title", "desc", "defs", "marker") for element in root.iter()):
        found.append("gambar harus memuat minimal satu bentuk atau teks.")
    return list(dict.fromkeys(found))


def validate(spec: dict) -> list[str]:
    root, issues = _parse(spec.get("svg"))
    if issues:
        return issues
    if _local(root.tag) != "svg" or _foreign(root.tag):
        return ["elemen akar harus <svg>."]
    return _structure_issues(root)


def _squash(text: str | None) -> str | None:
    return re.sub(r"\s+", " ", text) if text else None


def _clean(element: ET.Element) -> ET.Element:
    tag = _local(element.tag)
    cleaned = ET.Element(tag, {name: value.strip() for name, value in element.attrib.items()})
    cleaned.text = _squash(element.text) if tag in TEXT_ELEMENTS else None
    for child in element:
        node = _clean(child)
        node.tail = _squash(child.tail) if tag in ("text", "tspan") else None
        cleaned.append(node)
    return cleaned


def _cleaned_svg(svg: str) -> str:
    root, _ = _parse(svg)
    cleaned = _clean(root)
    cleaned.set("xmlns", SVG_NS)
    return ET.tostring(cleaned, encoding="unicode")


def finalize(spec: dict) -> dict:
    root, issues = _parse(spec.get("svg"))
    if issues or root is None:
        return spec
    result = {"svg": _cleaned_svg(spec["svg"])}
    if spec.get("deskripsi"):
        result["deskripsi"] = " ".join(str(spec["deskripsi"]).split())
    return result


def _render_and_describe(svg: str, context: str, feedback: str = "") -> str:
    digest = hashlib.sha256(f"{svg}\n{feedback}".encode("utf-8")).hexdigest()
    key = (CACHE_SOURCE, digest, common_config.VISION_MODEL, common_config.PROMPT_VERSION)
    with tempfile.TemporaryDirectory() as directory:
        return describe_cached(
            image_system(feedback=bool(feedback)), image_input("", context, feedback), key,
            lambda: svg_raster.render_png(svg, Path(directory)),
        )


def _described(svg: str, context: str, feedback: str = "") -> str:
    return speakable(_render_and_describe(svg, context, feedback)).strip()


def describe(spec: dict, context: str, issues: list[str]) -> dict:
    """Buat deskripsi bacaan dari gambar yang dirender lewat deskriptor gambar bersama; temuan bacaan masuk `issues`."""
    cleaned = _cleaned_svg(spec["svg"])
    root = _parse(cleaned)[0]
    text = _described(cleaned, context)
    if not text:
        raise ValueError("deskripsi gambar kosong")
    feedback = _omission_feedback(root, text)
    if feedback:
        retry = _described(cleaned, context, feedback)
        if retry and len(_number_issues(root, retry)) <= len(_number_issues(root, text)):
            text = retry
    issues.extend(description_issues(text))
    issues.extend(_number_issues(root, text))
    return {"svg": cleaned, "deskripsi": " ".join(text.split())}


def narrate(spec: dict) -> Narration:
    return Narration(" ".join(str(spec["deskripsi"]).split()))


KIND = StimulusKind(
    "gambar", 1, PROMPT_SCHEMA, KEYS, validate, narrate, finalize, raw_keys=("svg",), derived_keys=DERIVED_KEYS,
    describe=describe, available=lambda: svg_raster.available(),
)
