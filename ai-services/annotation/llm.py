import base64
import time
from functools import lru_cache
from pathlib import Path

from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI, RateLimitError

from annotation import config
from quiz import jsonutil

RETRYABLE = (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)
MAX_RETRIES = 5
BACKOFF_BASE = 2

JSON_FORMAT_REMINDER = (
    "\n\nPENTING: keluarkan HANYA satu objek JSON valid sesuai format yang diminta di atas -- "
    "tanpa markdown, tanpa teks lain, dan wajib sertakan SEMUA field yang diminta."
)


@lru_cache(maxsize=1)
def client() -> OpenAI:
    return OpenAI(base_url=config.OPENROUTER_BASE_URL, api_key=config.OPENROUTER_API_KEY)


def _create(**kwargs):
    delay = BACKOFF_BASE
    for attempt in range(MAX_RETRIES):
        try:
            return client().chat.completions.create(**kwargs)
        except RETRYABLE:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(delay)
            delay *= 2


def complete_text(system: str, user: str, model: str | None = None, max_tokens: int | None = None) -> str:
    response = _create(
        model=model or config.TEXT_MODEL,
        max_tokens=max_tokens or config.TEXT_MAX_TOKENS,
        extra_body={"reasoning": {"enabled": False}},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (response.choices[0].message.content or "").strip()


def complete_vision(system: str, user: str, image_path: Path, model: str | None = None) -> str:
    response = _create(
        model=model or config.VISION_MODEL,
        max_tokens=config.VISION_MAX_TOKENS,
        extra_body={"reasoning": {"enabled": False}},
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user},
                    {"type": "image_url", "image_url": {"url": _data_uri(image_path)}},
                ],
            },
        ],
    )
    return (response.choices[0].message.content or "").strip()


def complete_json(system: str, user: str, *, model: str | None = None, max_tokens: int | None = None,
                   required_keys: list[str] | None = None) -> dict:
    """Sama seperti `complete_text` tapi hasilnya diparse+divalidasi sebagai JSON. Kalau parse
    gagal atau ada `required_keys` yang hilang (model keluar kosong/salah format -- bisa karena
    feedback adversarial atau sekadar model meleset), retry SEKALI dengan reminder format yang
    lebih tegas ditempel ke prompt. Kalau masih gagal, raise ValueError dengan pesan bersih --
    bukan JSONDecodeError/KeyError mentah yang bisa bocor ke response API."""
    for attempt in range(2):
        raw = complete_text(system, user, model=model, max_tokens=max_tokens)
        try:
            data = jsonutil.parse_json(raw)
            missing = [k for k in (required_keys or []) if k not in data]
            if not missing:
                return data
        except Exception:
            missing = required_keys or ["<valid JSON>"]
        if attempt == 0:
            user = user + JSON_FORMAT_REMINDER
    raise ValueError(f"model tidak mengeluarkan JSON dengan format yang diharapkan setelah retry (field hilang: {missing})")


def _data_uri(image_path: Path) -> str:
    data = base64.standard_b64encode(image_path.read_bytes()).decode("ascii")
    suffix = image_path.suffix.lstrip(".").lower() or "jpeg"
    media = "jpeg" if suffix == "jpg" else suffix
    return f"data:image/{media};base64,{data}"
