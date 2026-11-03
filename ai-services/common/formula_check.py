import re

CLOSE_ROOT = "selesai akar"
CLOSE_FRACTION = "selesai pecahan"
CLOSE_POWER = "selesai pangkat"

STRAY_MARKS = re.compile(r"[?!]")
EMPTY_SCRIPT = re.compile(r"[_^]\s*\{\s*\}")
LEFTOVER_SYMBOLS = re.compile(r"[0-9^_{}\\+=×÷√∠△≤≥≠±∓∘∪∩∈∞Ͱ-Ͽ]")
ATOM = r"-?(?:[A-Za-z0-9.,]+|\\[A-Za-z]+)"
SIMPLE_ATOM = re.compile(ATOM)
SIMPLE_FRACTION = re.compile(r"\\[dt]?frac\{" + ATOM + r"\}\{" + ATOM + r"\}")
SIMPLE_TERM = re.compile(ATOM + r"!?(?:\^\{?-?[A-Za-z0-9.]+\}?)?")
STACKED_CLOSERS = re.compile(r"(?:tutup kurung(?: kurawal| siku)?\s*){2,}")
FUNCTION_PARENS = re.compile(r"\b[fghpqk] buka kurung \S+ tutup kurung")
BRACKET_KINDS = ("", " kurawal", " siku")
POINT_NAME = r"(?<![A-Za-z\\])[A-Z](?:'|\^\{\\prime\})?"
POINT_ARG = r"[^(),;\[\]]+?"
POINT_ARG_SEMICOLON = r"[^();\[\]]+?"
NAMED_POINT = re.compile(
    rf"{POINT_NAME}\s*\(\s*{POINT_ARG}(?:\s*,\s*{POINT_ARG}){{1,2}}\s*\)|"
    rf"{POINT_NAME}\s*\(\s*{POINT_ARG_SEMICOLON}(?:\s*;\s*{POINT_ARG_SEMICOLON}){{1,2}}\s*\)"
)
NOT_POINT_PREFIXES = ("\\sim", "\\mid")
PLUS_MINUS_READINGS = (("pm", "±", "plus atau minus"), ("mp", "∓", "minus atau plus"))
NOTATION_KEYWORDS = (
    (re.compile(r"\\vec(?![A-Za-z])"), ("vektor",)),
    (re.compile(r"\\overrightarrow(?![A-Za-z])"), ("vektor", "sinar")),
    (re.compile(r"\\int(?![A-Za-z])"), ("integral",)),
    (re.compile(r"\\sum(?![A-Za-z])"), ("jumlah",)),
    (re.compile(r"\\lim(?![A-Za-z])"), ("limit",)),
    (re.compile(r"\\begin\{pmatrix\}"), ("matriks",)),
)


def has_named_point(latex: str) -> bool:
    """Titik bernama seperti P(a, b); notasi bernilai (didahului '=' sesudahnya) atau distribusi (\\sim) bukan titik."""
    latex = " ".join(latex.split())
    for match in NAMED_POINT.finditer(latex):
        if not latex[match.end():].lstrip().startswith("=") and not latex[:match.start()].rstrip().endswith(NOT_POINT_PREFIXES):
            return True
    return False


def source_issues(latex: str) -> list[str]:
    """Temuan pada rumus sumber yang tampak rusak oleh OCR, terlepas dari bacaannya."""
    if EMPTY_SCRIPT.search(latex):
        return ["Rumus sumber memuat subskrip atau superskrip kosong; kemungkinan salah OCR, periksa terhadap sumber."]
    return []


def spoken_issues(latex: str, spoken: str) -> list[str]:
    """Periksa bacaan rumus terhadap strukturnya: simbol tersisa, penutup akar/pecahan/pangkat, kurung seimbang dan tidak beruntun."""
    issues = []
    text = " ".join(spoken.split()).lower()
    if LEFTOVER_SYMBOLS.search(text):
        issues.append("Bacaan masih memuat angka atau simbol; tulis semuanya dengan kata.")
    if STRAY_MARKS.search(text):
        issues.append("Bacaan memuat tanda tanya atau seru; tulis hanya lafal rumus tanpa kata atau tanda di luar rumus.")
    for name, marker, (needed, total) in (
        ("akar", CLOSE_ROOT, _roots(latex)),
        ("pecahan", CLOSE_FRACTION, _fractions(latex)),
        ("pangkat", CLOSE_POWER, _powers(latex)),
    ):
        found = text.count(marker)
        if found < needed:
            issues.append(f"Penutup '{marker}' kurang: ada {found}, perlu {needed} untuk struktur {name} yang majemuk.")
        elif found > total:
            issues.append(f"Penutup '{marker}' berlebih: ada {found}, padahal rumus hanya punya {total} struktur {name}.")
    for kind in BRACKET_KINDS:
        if len(re.findall(rf"buka kurung{kind}\b", text)) != len(re.findall(rf"tutup kurung{kind}\b", text)):
            issues.append("Jumlah 'buka kurung' dan 'tutup kurung' tidak sama.")
            break
    if STACKED_CLOSERS.search(text):
        issues.append("Ada 'tutup kurung' beruntun; ubah struktur kalimat atau sebut tingkat kurungnya.")
    if FUNCTION_PARENS.search(text):
        issues.append("Notasi fungsi dengan argumen sederhana dibaca 'f dari x', bukan 'f buka kurung x tutup kurung'.")
    issues.extend(_coordinate_issues(latex, text))
    issues.extend(_notation_issues(latex, text))
    return issues


def _notation_issues(latex: str, text: str) -> list[str]:
    return [
        f"Bacaan harus memuat kata '{words[0]}' untuk notasi ini."
        for pattern, words in NOTATION_KEYWORDS if pattern.search(latex) and not any(word in text for word in words)
    ]


def _coordinate_issues(latex: str, text: str) -> list[str]:
    issues = []
    if has_named_point(latex) and "koordinat" not in text:
        issues.append("Titik bernama dibaca 'titik P dengan koordinat a dan b', bukan seperti fungsi.")
    for command, symbol, reading in PLUS_MINUS_READINGS:
        if (re.search(r"\\" + command + r"(?![A-Za-z])", latex) or symbol in latex) and reading not in text:
            issues.append(f"Tanda plus-minus dibaca '{reading}'.")
    return issues


def complexity_issues(latex: str) -> list[str]:
    if _group_depth(latex) >= 4:
        return ["Rumus bersusun dalam; periksa apakah bacaannya jelas didengar."]
    return []


def _roots(latex: str) -> tuple[int, int]:
    groups = _command_groups(latex, "sqrt", 1, optional=True)
    return sum(not _is_simple(group[0]) for group in groups), len(groups)


def _fractions(latex: str) -> tuple[int, int]:
    groups = _command_groups(latex, "[dt]?frac", 2)
    return sum(any(not _fullmatch(SIMPLE_TERM, part) for part in group) for group in groups), len(groups)


def _powers(latex: str) -> tuple[int, int]:
    groups = [_read_group(latex, match.end()) for match in re.finditer(r"\^", latex)]
    return sum(1 for group in groups if group and not _is_simple_exponent(group[0])), latex.count("^")


def _is_simple_exponent(content: str) -> bool:
    return _is_simple(content) or _fullmatch(SIMPLE_FRACTION, content)


def _fullmatch(pattern: re.Pattern, content: str) -> bool:
    return bool(pattern.fullmatch(re.sub(r"\s+", "", content)))


def _command_groups(latex: str, name: str, count: int, optional: bool = False) -> list[list[str]]:
    results = []
    for match in re.finditer(r"\\" + name + r"(?![A-Za-z])", latex):
        position = match.end()
        if optional:
            position = _skip_optional(latex, position)
        groups = []
        for _ in range(count):
            group = _read_group(latex, position)
            if not group:
                break
            groups.append(group[0])
            position = group[1]
        if len(groups) == count:
            results.append(groups)
    return results


def _skip_optional(text: str, start: int) -> int:
    index = start
    while index < len(text) and text[index] == " ":
        index += 1
    if index < len(text) and text[index] == "[":
        end = text.find("]", index)
        return end + 1 if end != -1 else start
    return start


def _read_group(text: str, start: int):
    index = start
    while index < len(text) and text[index] == " ":
        index += 1
    if index >= len(text) or text[index] != "{":
        return None
    depth = 0
    for position in range(index, len(text)):
        char = text[position]
        escaped = position > 0 and text[position - 1] == "\\"
        if char == "{" and not escaped:
            depth += 1
        elif char == "}" and not escaped:
            depth -= 1
            if depth == 0:
                return text[index + 1:position], position + 1
    return None


def _is_simple(content: str) -> bool:
    return _fullmatch(SIMPLE_ATOM, content)


def _group_depth(latex: str) -> int:
    depth = best = 0
    for position, char in enumerate(latex):
        escaped = position > 0 and latex[position - 1] == "\\"
        if char == "{" and not escaped:
            depth += 1
            best = max(best, depth)
        elif char == "}" and not escaped:
            depth = max(0, depth - 1)
    return best
