import base64
import time
from functools import lru_cache
from pathlib import Path

from openai import APIConnectionError, APITimeoutError, BadRequestError, InternalServerError, OpenAI, RateLimitError

from annotation import config
from quiz import jsonutil

RETRYABLE = (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)
MAX_RETRIES = 5
BACKOFF_BASE = 2

JSON_FORMAT_REMINDER = (
    "\n\nPENTING: keluarkan HANYA satu objek JSON valid sesuai format yang diminta di atas -- "
    "tanpa markdown, tanpa teks lain, dan wajib sertakan SEMUA field yang diminta."
)


class ContentFilterError(ValueError):
    pass


@lru_cache(maxsize=1)
def client() -> OpenAI:
    if not (config.AZURE_OPENAI_API_KEY and config.AZURE_OPENAI_BASE_URL):
        raise RuntimeError("AZURE_OPENAI_API_KEY dan AZURE_OPENAI_ENDPOINT belum diisi di ai-services/.env")
    return OpenAI(base_url=config.AZURE_OPENAI_BASE_URL, api_key=config.AZURE_OPENAI_API_KEY)


def _create(*, model: str, max_tokens: int, effort: str, **kwargs):
    delay = BACKOFF_BASE
    for attempt in range(MAX_RETRIES):
        try:
            return client().chat.completions.create(
                model=model, max_completion_tokens=max_tokens, reasoning_effort=effort, **kwargs
            )
        except RETRYABLE:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(delay)
            delay *= 2
        except BadRequestError as e:
            if e.code == "content_filter":
                raise ContentFilterError("Permintaan ditolak filter keamanan: isinya dianggap mencoba memanipulasi instruksi sistem") from e
            raise


def complete_text(system: str, user: str, model: str | None = None, max_tokens: int | None = None,
                   effort: str | None = None) -> str:
    response = _create(
        model=model or config.TEXT_MODEL,
        max_tokens=max_tokens or config.TEXT_MAX_TOKENS,
        effort=effort or config.REASONING_EFFORT,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (response.choices[0].message.content or "").strip()


def complete_vision(system: str, user: str, image_path: Path, model: str | None = None) -> str:
    content = [
        {"type": "text", "text": user},
        {"type": "image_url", "image_url": {"url": _data_uri(image_path)}},
    ]
    for attempt in range(2):
        response = _create(
            model=model or config.VISION_MODEL,
            max_tokens=config.VISION_MAX_TOKENS,
            effort=config.VISION_EFFORT,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": content}],
        )
        try:
            description = str(jsonutil.parse_json(response.choices[0].message.content or "")["deskripsi"]).strip()
            if description:
                return description
        except Exception:
            pass
        if attempt == 0:
            content[0]["text"] += JSON_FORMAT_REMINDER
    raise ValueError("model tidak mengeluarkan deskripsi gambar dengan format JSON yang diharapkan setelah retry")


def complete_json(system: str, user: str, *, model: str | None = None, max_tokens: int | None = None,
                   required_keys: list[str] | None = None, effort: str | None = None) -> dict:
    """Sama seperti `complete_text` tapi hasilnya diparse+divalidasi sebagai JSON. Kalau parse
    gagal atau ada `required_keys` yang hilang (model keluar kosong/salah format -- bisa karena
    feedback adversarial atau sekadar model meleset), retry SEKALI dengan reminder format yang
    lebih tegas ditempel ke prompt. Kalau masih gagal, raise ValueError dengan pesan bersih --
    bukan JSONDecodeError/KeyError mentah yang bisa bocor ke response API."""
    for attempt in range(2):
        raw = complete_text(system, user, model=model, max_tokens=max_tokens, effort=effort)
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
