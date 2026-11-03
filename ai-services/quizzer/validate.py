import json
from concurrent.futures import ThreadPoolExecutor

from quizzer import config, prompts
from quizzer.stimulus import registry
from common import llm

MAX_TOKENS = 3072
AUDIT_FLAGS = (
    ("data_lengkap", False, "Langkah atau kunci memakai data yang tidak ada di soal atau stimulus."),
    ("opsi_di_luar_soal", True, "Ada opsi yang merujuk hal yang tidak ada di soal atau stimulus."),
    ("opsi_kontradiktif", True, "Ada opsi yang bertentangan dengan dirinya sendiri."),
)


def validate_soal(source_text: str, question_text: str, options: dict, correct_option: str, stimulus_text: str = "") -> dict:
    """Chain 4: re-derive jawaban independen dari sumber yang sama, bandingkan ke hasil Generation."""
    prompt = prompts.validate_input(source_text, question_text, options, stimulus_text)
    derived = llm.complete_json(prompts.VALIDATE_SYSTEM, prompt, model=config.QUIZ_VALIDATOR_MODEL,
                                 max_tokens=MAX_TOKENS, required_keys=["correct_option"])
    return {
        "matches": str(derived.get("correct_option", "")).strip().upper().rstrip(".") == correct_option,
        "derived_option": derived.get("correct_option"),
        "derived_langkah": derived.get("langkah", []),
    }


def audit_soal(source_text: str, soal: dict, stimulus_text: str = "", markup_text: str = "") -> dict:
    return llm.complete_json(
        prompts.AUDIT_SYSTEM, prompts.audit_input(source_text, soal, stimulus_text, markup_text),
        model=config.QUIZ_VALIDATOR_MODEL, max_tokens=config.AUDIT_MAX_TOKENS,
        required_keys=["langkah_valid", "kesimpulan_konsisten", "opsi_lain_benar", "stem_ambigu", "masalah"],
    )


def verify_soal(source_text: str, data: dict, stimulus_text: str = "") -> dict:
    """Jawab buta dan audit justifikasi oleh model validator; tidak pernah melempar, kegagalan dicatat sebagai masalah."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        blind = pool.submit(_safe, validate_soal, source_text, data["question_text"], data["options"],
                            data["correct_option"], stimulus_text)
        audit = pool.submit(_safe, audit_soal, source_text, data, stimulus_text, markup_text(data))
        blind_result, audit_result = blind.result(), audit.result()
    unavailable = [f"{name} oleh validator tidak dapat dijalankan ({type(result).__name__})."
                   for name, result in (("Jawab buta", blind_result), ("Audit langkah dan kesimpulan", audit_result))
                   if isinstance(result, Exception)]
    return {"blind": blind_result, "audit": audit_result, "unavailable": unavailable,
            "issues": verification_issues(data, blind_result, audit_result, bool(stimulus_text))}


def verification_issues(data: dict, blind, audit, has_stimulus: bool) -> list[str]:
    issues = []
    if not isinstance(blind, Exception) and not blind["matches"]:
        issues.append(
            f"Validasi independen sampai ke jawaban {blind['derived_option']}, berbeda dari kunci "
            f"{data['correct_option']}. Langkah validasi: {'; '.join(map(str, blind['derived_langkah']))}"
        )
    if isinstance(audit, Exception):
        return issues
    if audit.get("langkah_valid") is False:
        issues.append("Langkah penyelesaian tidak valid atau tidak mengarah ke kunci.")
    if audit.get("kesimpulan_konsisten") is False:
        issues.append("Kesimpulan tidak konsisten dengan langkah dan kunci.")
    claimed = audit.get("opsi_lain_benar")
    others = [label for label in (claimed if isinstance(claimed, list) else []) if label != data["correct_option"]]
    if others:
        issues.append(f"Opsi {', '.join(map(str, others))} juga benar.")
    if audit.get("stem_ambigu") is True:
        issues.append("Stem ambigu.")
    for key, expected, message in AUDIT_FLAGS:
        if audit.get(key) is expected:
            issues.append(message)
    if audit.get("readable_setia") is False:
        issues.append("Teks siap-baca tidak setia pada markup LaTeX atau tabel.")
    if has_stimulus and audit.get("stimulus_dibutuhkan") is False:
        issues.append("Stimulus tidak dibutuhkan untuk menjawab soal.")
    problems = audit.get("masalah")
    issues.extend(str(item) for item in (problems if isinstance(problems, list) else []))
    return issues


def is_blocking(verification: dict, data: dict) -> bool:
    """True bila soal tidak bisa dijawab dengan benar: jawab buta berbeda, langkah tidak valid, opsi lain juga benar, atau data atau opsi merujuk hal di luar soal."""
    blind, audit = verification.get("blind"), verification.get("audit")
    if blind is not None and not isinstance(blind, Exception) and not blind["matches"]:
        return True
    if not isinstance(audit, dict):
        return False
    claimed = audit.get("opsi_lain_benar")
    others = [label for label in (claimed if isinstance(claimed, list) else []) if label != data["correct_option"]]
    return audit.get("langkah_valid") is False or bool(others) or audit.get("data_lengkap") is False or audit.get("opsi_di_luar_soal") is True


def markup_text(data: dict) -> str:
    parts = []
    if data.get("markup"):
        parts.append(json.dumps(data["markup"], ensure_ascii=False))
    stimulus = data.get("stimulus")
    if isinstance(stimulus, dict) and stimulus.get("source_markup"):
        parts.append(stimulus["source_markup"])
    if registry.is_typed(stimulus):
        parts.append(json.dumps({"jenis": stimulus["jenis"], "spesifikasi": stimulus.get("spesifikasi")}, ensure_ascii=False))
    return "\n".join(parts)


def _safe(fn, *args):
    try:
        return fn(*args)
    except Exception as exc:
        return exc
