import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

AI_SERVICES = Path(r"E:\Lydera\ai-services")
sys.path.insert(0, str(AI_SERVICES))

from annotation import llm
from quiz import validate
from quiz.segment import build_segments

EVAL_DIR = AI_SERVICES / "chatbot" / "eval"
OUT_DIR = Path(__file__).parent

JUDGES = ["grok-4.3", "DeepSeek-V3.2", "Llama-3.3-70B-Instruct"]


def find_segment(soal: dict, segments: list):
    for seg in segments:
        if seg.reading_order_start <= soal["reading_order_start"] <= soal["reading_order_end"] <= seg.reading_order_end:
            return seg
    for seg in segments:
        if seg.reading_order_start <= soal["reading_order_start"] <= seg.reading_order_end:
            return seg
    return segments[0]


def derive_option(segment, soal: dict, model: str) -> str | None:
    stim_text = (soal.get("stimulus") or {}).get("readable_text", "")
    prompt = validate.build_prompt(segment, soal["question_text"], soal["options"], stim_text)
    try:
        result = llm.complete_json(validate.SYSTEM, prompt, model=model, max_tokens=validate.MAX_TOKENS,
                                    required_keys=["correct_option"])
        return result.get("correct_option")
    except Exception:
        return None


def majority(options: list[str]) -> str | None:
    counts = {}
    for o in options:
        if o:
            counts[o] = counts.get(o, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


def main():
    samples = json.loads((OUT_DIR / "generated_soal.json").read_text(encoding="utf-8"))
    segments_by_bab = {
        "bab1": build_segments(1, json.loads((EVAL_DIR / "blocks" / "bab1.json").read_text(encoding="utf-8"))),
        "bab2": build_segments(2, json.loads((EVAL_DIR / "blocks" / "bab2.json").read_text(encoding="utf-8"))),
    }

    rows = []
    for bab, items in samples.items():
        for item in items:
            soal = item["soal"]
            seg = find_segment(soal, segments_by_bab[bab])
            derived = {m: derive_option(seg, soal, m) for m in JUDGES}
            voted = majority(list(derived.values()))
            rows.append({
                "bab": bab, "bloom_level": soal["bloom_level"],
                "generator_answer": soal["correct_option"], "derived": derived, "voted": voted,
                "matches_majority": voted == soal["correct_option"],
                "question": soal["question_text"][:60],
            })
            print(f"{bab} | C{soal['bloom_level']} | generator={soal['correct_option']} derived={derived} "
                  f"voted={voted} match={voted == soal['correct_option']}")

    (OUT_DIR / "answer_results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    for m in JUDGES:
        acc = sum(1 for r in rows if r["derived"][m] == r["generator_answer"]) / len(rows)
        print(f"{m:25} matches_rate={acc:.3f}")
    maj_acc = sum(r["matches_majority"] for r in rows) / len(rows)
    print(f"{'Mayoritas (3 model)':25} matches_rate={maj_acc:.3f} ({sum(r['matches_majority'] for r in rows)}/{len(rows)})")


if __name__ == "__main__":
    main()
