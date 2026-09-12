import json
import re

_INVALID_ESCAPE = re.compile(r'\\(?!["\\/]|u[0-9a-fA-F]{4})')


def parse_json(raw: str) -> dict:
    """Ambil objek JSON dari hasil LLM, toleran terhadap code fence markdown (```json ... ```)
    dan backslash liar (mis. notasi LaTeX \\% yang bukan escape sequence JSON valid)."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(_INVALID_ESCAPE.sub(r"\\\\", text))
