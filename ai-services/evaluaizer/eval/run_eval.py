import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

AI_SERVICES = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AI_SERVICES))

from common import llm
from evaluaizer import evaluate
from quizzer import config as quizzer_config

CASES = json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8"))
REPEATS = 3

JUDGE_SYSTEM = (
    "Anda menilai penjelasan kesalahan untuk siswa. Anda menerima soal, langkah kunci yang benar, kesimpulan, jawaban siswa, "
    "dan daftar poin penjelasan. Keluarkan HANYA JSON: "
    '{"final_correct": true, "math_accurate": true, "continues_from_error": true, "mentions_missing_notes": false, "reason": "..."}. '
    "final_correct: poin terakhir atau poin-poin menyatakan jawaban akhir yang benar sesuai kesimpulan kunci. "
    "math_accurate: tidak ada pernyataan matematika yang salah dibanding langkah kunci. "
    "continues_from_error: penjelasan perbaikan dimulai dari letak kesalahan siswa lalu berlanjut sampai kesimpulan. "
    "mentions_missing_notes: ada kalimat yang menyebut bahwa catatan atau langkah siswa tidak ada atau tidak disertakan."
)


def run_case(case: dict, repeat: int) -> dict:
    result = evaluate.evaluate_scratchwork(
        case["source"], case["stimulus"], case["question"], case["options"], case["correct_option"], case["key_steps"],
        case["conclusion"], case["student_option"], case["student_steps"],
    )
    judge = judge_result(case, result)
    return {
        "id": case["id"], "repeat": repeat, "result": result, "judge": judge,
        "divergence_ok": result["divergence_step"] in case["accepted_divergence"],
        "type_ok": result["error_type"] in case["accepted_types"],
        "clean": not result["issues"],
    }


def judge_result(case: dict, result: dict) -> dict:
    options = "\n".join(f"{label}. {text}" for label, text in case["options"].items())
    key = "\n".join(f"{i}. {text}" for i, text in enumerate(case["key_steps"], start=1))
    student = "\n".join(f"{i}. {text}" for i, text in enumerate(case["student_steps"], start=1)) or "(tidak menulis langkah)"
    points = "\n".join(f"{i}. {point['point']}" for i, point in enumerate(result["justification_points"], start=1))
    user = (
        f"Soal: {case['question']}\n{options}\nJawaban benar: {case['correct_option']}\nLangkah kunci:\n{key}\n"
        f"Kesimpulan: {case['conclusion']}\nJawaban siswa: {case['student_option']}\nCatatan siswa:\n{student}\n\n"
        f"Poin penjelasan:\n{points}"
    )
    try:
        return llm.complete_json(JUDGE_SYSTEM, user, model=quizzer_config.QUIZ_VALIDATOR_MODEL, max_tokens=800,
                                 required_keys=["final_correct", "math_accurate", "continues_from_error", "mentions_missing_notes"])
    except Exception as error:
        return {"error": str(error)}


def summarize(rows: list[dict]) -> None:
    total = len(rows)
    judged = [row for row in rows if "error" not in row["judge"]]
    print(f"\nTotal {total} hasil ({len(CASES)} kasus x {REPEATS} ulangan)")
    print(f"divergence_step sesuai : {sum(r['divergence_ok'] for r in rows)}/{total}")
    print(f"error_type diterima    : {sum(r['type_ok'] for r in rows)}/{total}")
    print(f"lolos pemeriksa kode   : {sum(r['clean'] for r in rows)}/{total}")
    print(f"juri tersedia          : {len(judged)}/{total}")
    for key in ("final_correct", "math_accurate", "continues_from_error"):
        print(f"juri {key:22}: {sum(bool(r['judge'][key]) for r in judged)}/{len(judged)}")
    print(f"juri menyebut catatan hilang: {sum(bool(r['judge']['mentions_missing_notes']) for r in judged)}/{len(judged)}")
    for case in CASES:
        group = [row for row in rows if row["id"] == case["id"]]
        steps = [row["result"]["divergence_step"] for row in group]
        types = [row["result"]["error_type"] for row in group]
        print(f"- {case['id']:28} divergence {steps} (diterima {case['accepted_divergence']}) tipe {types} "
              f"bersih {[r['clean'] for r in group]}")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("pemakaian: python -m evaluaizer.eval.run_eval <berkas_keluaran.json>")
    jobs = [(case, repeat) for case in CASES for repeat in range(REPEATS)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda job: run_case(*job), jobs))
    Path(sys.argv[1]).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    summarize(rows)


if __name__ == "__main__":
    main()
