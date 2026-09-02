import base64
from functools import lru_cache
from pathlib import Path

from openai import OpenAI

import config


@lru_cache(maxsize=1)
def client() -> OpenAI:
    return OpenAI(base_url=config.OPENROUTER_BASE_URL, api_key=config.OPENROUTER_API_KEY)


def complete_text(system: str, user: str, model: str | None = None) -> str:
    response = client().chat.completions.create(
        model=model or config.TEXT_MODEL,
        max_tokens=config.TEXT_MAX_TOKENS,
        extra_body={"reasoning": {"enabled": False}},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (response.choices[0].message.content or "").strip()


def complete_vision(system: str, user: str, image_path: Path, model: str | None = None) -> str:
    response = client().chat.completions.create(
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


def _data_uri(image_path: Path) -> str:
    data = base64.standard_b64encode(image_path.read_bytes()).decode("ascii")
    suffix = image_path.suffix.lstrip(".").lower() or "jpeg"
    media = "jpeg" if suffix == "jpg" else suffix
    return f"data:image/{media};base64,{data}"
