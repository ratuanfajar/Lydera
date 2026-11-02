import random
import re

LABELS = ("A", "B", "C", "D")
LETTER_REFERENCE = re.compile(r"\b([Oo]psi|[Jj]awaban|[Pp]ilihan)(\s*:?\s+)([A-D](?:\s*(?:,|dan|atau)\s*[A-D])*)\b")


def balanced_targets(count: int, rng: random.Random) -> list[str]:
    offset = rng.randrange(len(LABELS))
    targets = [LABELS[(i + offset) % len(LABELS)] for i in range(count)]
    rng.shuffle(targets)
    return targets


def reorder_options(data: dict, target: str, rng: random.Random) -> dict:
    options = data["options"]
    correct = str(data["correct_option"]).strip().upper()
    if set(options) != set(LABELS) or correct not in options:
        return data
    others = [label for label in options if label != correct]
    rng.shuffle(others)
    new_order = others[:]
    new_order.insert(LABELS.index(target), correct)
    mapping = {old: new for old, new in zip(new_order, LABELS)}
    data["options"] = {mapping[old]: options[old] for old in new_order}
    data["correct_option"] = target
    data["langkah"] = [_remap_letters(step, mapping) for step in data["langkah"]]
    data["kesimpulan"] = _remap_letters(data["kesimpulan"], mapping)
    markup = data.get("markup")
    if markup:
        markup["options"] = {mapping[old]: markup["options"][old] for old in new_order}
        markup["langkah"] = [_remap_letters(step, mapping) for step in markup["langkah"]]
        markup["kesimpulan"] = _remap_letters(markup["kesimpulan"], mapping)
    return data


def _remap_letters(text: str, mapping: dict) -> str:
    def replace(match):
        letters = re.sub(r"[A-D]", lambda m: mapping[m.group(0)], match.group(3))
        return f"{match.group(1)}{match.group(2)}{letters}"

    return LETTER_REFERENCE.sub(replace, text)
