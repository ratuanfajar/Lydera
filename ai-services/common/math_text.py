import re
from html import escape
from html.parser import HTMLParser

from common.formula import convert_checked
from common.formula_check import complexity_issues
from common.parallel import parallel_map
from common.speakable import manual_reading_issues

MAX_SUMMARY_COLUMNS = 6
GREEK_NAMES = {
    "α": "alfa", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon", "θ": "teta", "λ": "lambda", "μ": "mu",
    "π": "pi", "ρ": "rho", "σ": "sigma", "τ": "tau", "φ": "fi", "ω": "omega", "Δ": "delta", "Σ": "sigma", "Ω": "omega",
    "ξ": "ksi", "η": "eta", "ζ": "zeta", "κ": "kapa", "ν": "nu", "ψ": "psi", "χ": "kai", "ϕ": "fi", "ϑ": "teta", "ϵ": "epsilon",
    "Γ": "gamma", "Θ": "teta", "Φ": "fi", "Π": "pi", "Ψ": "psi", "Ξ": "ksi",
}
TRAILING_TITIK = re.compile(r"\btitik\s*$", re.IGNORECASE)
ENGLISH_GREEK = re.compile(r"\b(alpha|theta|phi|varphi|vartheta|varepsilon)\b", re.IGNORECASE)
ENGLISH_GREEK_NAMES = {"alpha": "alfa", "theta": "teta", "phi": "fi", "varphi": "fi", "vartheta": "teta", "varepsilon": "epsilon"}
HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")
MATH_SPAN = re.compile(r"(?<!\\)\$\$.+?(?<!\\)\$\$|(?<!\\)\$.+?(?<!\\)\$", re.DOTALL)
TABLE_HTML = re.compile(r"<table\b.*?</table>", re.DOTALL | re.IGNORECASE)
LATEX_PAIRS = ((re.compile(r"\\left(?![A-Za-z])"), re.compile(r"\\right(?![A-Za-z])"), "left", "right"),
               (re.compile(r"\\begin(?![A-Za-z])"), re.compile(r"\\end(?![A-Za-z])"), "begin", "end"))


def split_math(text: str) -> list[tuple[bool, str]]:
    parts, cursor = [], 0
    for match in MATH_SPAN.finditer(text):
        if match.start() > cursor:
            parts.append((False, text[cursor:match.start()]))
        parts.append((True, _strip_delimiters(match.group())))
        cursor = match.end()
    if cursor < len(text):
        parts.append((False, text[cursor:]))
    return parts


def plain_text_issues(strings: list[str]) -> list[str]:
    """Temuan bacaan layar pada bagian teks di luar rumus $...$ (rumus diverbalisasi sistem); string kosong dilewati."""
    issues: list[str] = []
    for text in strings:
        outside = " ".join(content for is_math, content in split_math(str(text or "")) if not is_math).strip()
        if outside:
            issues.extend(manual_reading_issues(outside))
    return list(dict.fromkeys(issues))


def readable_texts(markups: list[str], issues: list[str] | None = None) -> list[str]:
    """Ubah teks berisi LaTeX inline ($...$) menjadi teks siap-baca; setiap rumus unik diverbalisasi sekali, temuan dikumpulkan ke `issues`."""
    split = [split_math(markup) for markup in markups]
    formulas = sorted({content for parts in split for is_math, content in parts if is_math})
    results = parallel_map(convert_checked, formulas)
    spoken = {latex: text for latex, (text, _) in zip(formulas, results)}
    if issues is not None:
        for latex, (_, found) in zip(formulas, results):
            issues.extend(f"Bacaan rumus '{latex[:40]}': {issue}" for issue in [*found, *complexity_issues(latex)])
    return [join_spoken([(is_math, spoken[c] if is_math else c) for is_math, c in parts]) for parts in split]


def join_spoken(parts: list[tuple[bool, str]]) -> str:
    """Gabungkan bagian teks dan bacaan rumus (is_math=True sudah diverbalisasi); 'titik' ganda dibuang dan huruf Yunani dieja."""
    joined = ""
    for is_math, content in parts:
        drop = is_math and content.startswith("titik ") and TRAILING_TITIK.search(joined)
        joined += content[len("titik "):] if drop else content
    return spell_greek(joined)


def strip_tags(text: str, replacement: str = "") -> str:
    return HTML_TAG.sub(replacement, text)


def normalize_spacing(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"\s+([.,;:!?])", r"\1", text).strip()


def table_html(table: dict) -> str:
    head = "".join(f"<th>{escape(_text(cell))}</th>" for cell in table["kolom"])
    rows = "".join("<tr>" + "".join(f"<td>{escape(_text(cell))}</td>" for cell in row) + "</tr>" for row in table["baris"])
    caption = f"<caption>{escape(_text(table['judul']))}</caption>" if table.get("judul") else ""
    return f"<table>{caption}<thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"


def split_table(markup: str) -> tuple[str, dict | None]:
    """Pisahkan teks dan tabel HTML dari satu markup; tabel yang tidak bisa diparse menjadi None."""
    match = TABLE_HTML.search(markup)
    if not match:
        return markup.strip(), None
    return (markup[:match.start()] + markup[match.end():]).strip(), parse_table_html(match.group())


def spoken_table(table: dict, issues: list[str] | None = None) -> dict:
    """Bentuk tabel yang dibacakan pembaca layar: rumus diverbalisasi, huruf Yunani dieja, sel kosong 'kosong', nama kolom unik."""
    cells = [_text(table.get("judul")), *map(_text, table["kolom"]), *(_text(cell) for row in table["baris"] for cell in row)]
    spoken = iter(readable_texts(cells, issues))
    title = next(spoken)
    columns = _unique_columns([next(spoken) for _ in table["kolom"]])
    rows = [[next(spoken) or "kosong" for _ in row] for row in table["baris"]]
    return {"judul": title or None, "kolom": columns, "baris": rows}


def table_readable(spoken: dict) -> str:
    """Linearisasi tabel yang sudah dibacakan (keluaran spoken_table): judul kolom disebut, lalu baris demi baris."""
    parts = [_table_heading(spoken["judul"] or ""), f"Ada {len(spoken['kolom'])} kolom: {_join_words(spoken['kolom'])}."]
    for number, row in enumerate(spoken["baris"], start=1):
        pairs = "; ".join(f"{column}: {cell}" for column, cell in zip(spoken["kolom"], row))
        parts.append(f"Baris {number}. {pairs}.")
    return " ".join(parts)


def table_summary(spoken: dict, topic: str = "") -> str:
    """Ringkasan tabel yang sudah dibacakan; kalimat pembuka dari topik model atau judul tabel."""
    names = spoken["kolom"]
    shown = names if len(names) <= MAX_SUMMARY_COLUMNS else [*names[:MAX_SUMMARY_COLUMNS], f"{len(names) - MAX_SUMMARY_COLUMNS} kolom lainnya"]
    head = _sentence(spell_greek(topic)) or _table_heading(spoken["judul"] or "")
    return f"{head} Ada {len(names)} kolom dan {len(spoken['baris'])} baris data. Nama kolomnya adalah {_join_words(shown)}."


def latex_issues(markup: str) -> list[str]:
    issues = []
    if "$" in MATH_SPAN.sub("", markup).replace("\\$", ""):
        issues.append("Tanda $ tidak berpasangan.")
    for _, content in (part for part in split_math(markup) if part[0]):
        if not content.strip():
            issues.append("Ada rumus kosong di antara tanda $.")
        elif _brace_depth_broken(content):
            issues.append(f"Kurung kurawal LaTeX tidak seimbang: {content[:40]}")
        for opening, closing, open_name, close_name in LATEX_PAIRS:
            if len(opening.findall(content)) != len(closing.findall(content)):
                issues.append(f"\\{open_name} dan \\{close_name} tidak berpasangan: {content[:40]}")
    return issues


def table_issues(table) -> list[str]:
    if not isinstance(table, dict) or not isinstance(table.get("kolom"), list) or not isinstance(table.get("baris"), list):
        return ["Tabel harus berisi 'kolom' (daftar) dan 'baris' (daftar baris)."]
    if not table["kolom"] or not table["baris"]:
        return ["Tabel tidak boleh kosong."]
    width = len(table["kolom"])
    if any(not isinstance(row, list) or len(row) != width for row in table["baris"]):
        return ["Setiap baris tabel harus punya jumlah sel yang sama dengan jumlah kolom."]
    return []


def parse_table_html(html: str) -> dict | None:
    parser = _TableParser()
    parser.feed(html)
    if not parser.header or not parser.rows:
        return None
    table = {"judul": parser.caption or None, "kolom": parser.header, "baris": parser.rows}
    return table if not table_issues(table) else None


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.caption, self.header, self.rows = "", [], []
        self._row, self._cell, self._row_has_th = None, None, False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row, self._row_has_th = [], False
        elif tag in ("th", "td", "caption"):
            self._cell = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("th", "td") and self._cell is not None and self._row is not None:
            self._row.append("".join(self._cell).strip())
            self._row_has_th = self._row_has_th or tag == "th"
            self._cell = None
        elif tag == "caption" and self._cell is not None:
            self.caption, self._cell = "".join(self._cell).strip(), None
        elif tag == "tr" and self._row is not None:
            if self._row_has_th and not self.header:
                self.header = self._row
            else:
                self.rows.append(self._row)
            self._row = None


def _strip_delimiters(value: str) -> str:
    value = value.strip()
    if value.startswith("$$") and value.endswith("$$"):
        return value[2:-2].strip()
    return value[1:-1].strip() if value.startswith("$") and value.endswith("$") else value


def _brace_depth_broken(content: str) -> bool:
    depth = 0
    for index, char in enumerate(content):
        escaped = index > 0 and content[index - 1] == "\\"
        if char == "{" and not escaped:
            depth += 1
        elif char == "}" and not escaped:
            depth -= 1
            if depth < 0:
                return True
    return depth != 0


def _table_heading(title: str) -> str:
    title = title.strip().rstrip(".:;")
    if not title:
        return "Tabel tanpa judul."
    return f"{title}." if title.lower().startswith("tabel") else f"Tabel {title}."


def spell_greek(text: str) -> str:
    """Eja huruf Yunani (simbol dan nama Inggris) dengan nama Indonesia, rapikan spasi dan kurung."""
    named = ENGLISH_GREEK.sub(lambda match: ENGLISH_GREEK_NAMES[match.group().lower()], text)
    spelled = normalize_spacing("".join(f" {GREEK_NAMES[char]} " if char in GREEK_NAMES else char for char in named))
    return re.sub(r"\s+([)\]])", r"\1", re.sub(r"([(\[])\s+", r"\1", spelled))


def _sentence(text: str) -> str:
    text = text.strip()
    return text if not text or text[-1] in ".!?" else text + "."


def _text(value) -> str:
    return "" if value is None else str(value)


def _unique_columns(names: list[str]) -> list[str]:
    named = [name or f"Kolom {index}" for index, name in enumerate(names, start=1)]
    return [
        f"{name} (kolom {index})" if named.count(name) > 1 else name
        for index, name in enumerate(named, start=1)
    ]


def _join_words(items: list[str]) -> str:
    if len(items) <= 2:
        return " dan ".join(items)
    return ", ".join(items[:-1]) + f", dan {items[-1]}"
