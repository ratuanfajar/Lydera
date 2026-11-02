import re

from annoter import image
from annoter.preprocess import Block, Route
from annoter.speakable import description_issues
from annoter.table import TableResult
from common.notation_check import has_raw_notation

DEGRADED_EMPTY_CELL_RATIO = 0.3
TABLE_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)


def review_priority(block: Block) -> str:
    if block.route in (Route.HEADING, Route.TEXT):
        return "low"
    if block.route == Route.TABLE and table_degraded(block.table_html):
        return "high"
    return "normal"


def escalate(block: Block, flagged: bool) -> str:
    return "high" if flagged else review_priority(block)


def table_flagged(result: TableResult) -> bool:
    return bool(result.issues) or has_raw_notation(result.text)


def image_priority(result: image.ImageAnnotation) -> str:
    if result.kind == image.DECORATIVE:
        return "normal"
    if result.uncertain or not result.text or result.kind in image.HIGH_REVIEW_KINDS or description_issues(result.text):
        return "high"
    return "normal"


def table_degraded(html: str) -> bool:
    if "�" in html:
        return True
    cells = TABLE_CELL.findall(html)
    if not cells:
        return False
    empty = sum(1 for cell in cells if not cell.strip())
    return empty / len(cells) > DEGRADED_EMPTY_CELL_RATIO
