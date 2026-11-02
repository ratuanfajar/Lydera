import json
import re

_INVALID_ESCAPE = re.compile(r'\\(?!["\\/]|u[0-9a-fA-F]{4})')

_LATEX_BACKSLASH = re.compile(
    r'(?P<keep>\\\\|\\["/]|\\u[0-9a-fA-F]{4})'
    r'|(?P<latex>\\(?=[bfrt][A-Za-z]|n(?:eq|ot|eg|abla|mid|parallel|sim|leq|geq|less|gtr|exists|cong|rightarrow|leftarrow'
    r'|subset|supset|ewline|[uei](?![A-Za-z]))))'
    r'|(?P<valid>\\[bfnrt])'
    r'|(?P<lone>\\)'
)


def parse_json(raw: str, latex: bool = False) -> dict:
    """Parse JSON keluaran LLM; latex=True melindungi perintah LaTeX (\\frac, \\times, \\neq) yang ditulis dengan satu backslash."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    if latex:
        return json.loads(_LATEX_BACKSLASH.sub(_keep_or_double, text))
    return json.loads(_INVALID_ESCAPE.sub(r"\\\\", text))


def _keep_or_double(match: re.Match) -> str:
    return "\\\\" if match.lastgroup in ("latex", "lone") else match.group()
