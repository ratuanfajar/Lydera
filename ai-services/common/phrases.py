import re

UNREADABLE = "tidak terbaca"
FORMULA_UNREADABLE = f"rumus {UNREADABLE}"
UNCERTAIN_READING = re.compile(rf"{UNREADABLE}|tidak dapat dibaca", re.IGNORECASE)
