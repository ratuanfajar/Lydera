import json
from dataclasses import dataclass

from annoter import config as annoter_config
from annoter import prompts
from annoter.preprocess import Block
from annoter.speakable import speakable
from common import cache, config, llm

NO_KIND = ""
DECORATIVE = "dekoratif"
CONTEXT_KIND = "ilustrasi_konteks"
GENERAL = "umum"
HIGH_REVIEW_KINDS = frozenset({"grafik", "diagram", "teks_di_gambar"})


@dataclass
class ImageAnnotation:
    kind: str
    text: str
    uncertain: bool = False


def annotate_image(block: Block, context: str = "") -> ImageAnnotation:
    if not (block.image_path and block.image_path.exists()):
        return ImageAnnotation(NO_KIND, "")
    kind, uncertain = classify_image(block, context)
    if kind == DECORATIVE:
        return ImageAnnotation(kind, "")
    prompt_kind = kind if kind in prompts.KIND_RULES and not uncertain else GENERAL
    stored_kind = kind if kind in prompts.IMAGE_KINDS else NO_KIND
    return ImageAnnotation(stored_kind, speakable(_describe(block, context, prompt_kind)), uncertain)


def classify_image(block: Block, context: str) -> tuple[str, bool]:
    near_context = context[: annoter_config.CLASSIFY_CONTEXT_CHARS]
    first = _classify(block, "")
    second = _classify(block, near_context)
    return resolve_final(_arbitrate(block, near_context, first, second))


def resolve_final(final: dict) -> tuple[str, bool]:
    kind = final["jenis"]
    confident = _confidence(final) >= annoter_config.CLASSIFY_MIN_CONFIDENCE
    if kind == DECORATIVE and not confident:
        return CONTEXT_KIND, True
    return kind, not (kind in prompts.IMAGE_KINDS and confident)


def _describe(block: Block, context: str, prompt_kind: str) -> str:
    key = _key(block, prompt_kind)
    cached = cache.get("image", *key)
    if cached is None:
        system = prompts.image_system() if prompt_kind == GENERAL else prompts.image_kind_system(prompt_kind)
        cached = llm.complete_vision(system, prompts.image_input(block.caption, context), block.image_path)
        cache.put("image", cached, *key)
    return cached


def _classify(block: Block, context: str) -> dict:
    return _classification(
        "image_kind", _key(block, context), prompts.image_classifier_system(),
        prompts.image_classifier_input(block.caption, context), block,
    )


def _arbitrate(block: Block, context: str, first: dict, second: dict) -> dict:
    return _classification(
        "image_kind_final", _key(block, context, json.dumps([first, second])), prompts.image_arbiter_system(),
        prompts.image_arbiter_input(block.caption, context, first, second), block,
    )


def _classification(namespace: str, key: tuple, system: str, user: str, block: Block) -> dict:
    cached = cache.get(namespace, *key)
    if cached is None:
        data = llm.complete_vision_json(
            system, user, block.image_path, max_tokens=annoter_config.CLASSIFY_MAX_TOKENS, required_keys=("jenis",)
        )
        cached = json.dumps(
            {"jenis": str(data["jenis"]).strip(), "yakin": data.get("yakin"), "alasan": data.get("alasan", "")},
            ensure_ascii=False,
        )
        cache.put(namespace, cached, *key)
    return json.loads(cached)


def _key(block: Block, *extra: str) -> tuple:
    return (block.image_path.stem, config.VISION_MODEL, config.PROMPT_VERSION, *extra)


def _confidence(result: dict) -> int:
    try:
        return int(result.get("yakin") or 0)
    except (TypeError, ValueError):
        return 0
