from dataclasses import dataclass
from typing import Callable


@dataclass
class Narration:
    readable_text: str
    tabel: dict | None = None
    ringkasan: str | None = None


@dataclass(frozen=True)
class StimulusKind:
    name: str
    schema_version: int
    prompt_schema: str
    keys: tuple[str, ...]
    validate: Callable[[dict], list[str]]
    narrate: Callable[[dict], Narration]
    finalize: Callable[[dict], dict] = lambda spec: spec
    raw_keys: tuple[str, ...] = ()
    derived_keys: tuple[str, ...] = ()
    describe: Callable[[dict, str, list[str]], dict] | None = None
    available: Callable[[], bool] = lambda: True
