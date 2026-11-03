import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

AI_SERVICES = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AI_SERVICES))

from evaluaizer import evaluate

CASES = json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8"))
REPEATS = 3


def run_case(case: dict, repeat: int) -> dict:
    try:
        result = evaluate.evaluate_scratchwork(
            case["source"], case["stimulus"], case["question"], case["options"], case["correct_option"], case["key_steps"],
            case["conclusion"], case["student_option"], case["student_steps"],
        )
    except Exception as exc:
        return {"id": case["id"], "repeat": repeat, "error": f"{type(exc).__name__}: {exc}"[:300]}
    return {
        "id": case["id"], "repeat": repeat, "result": result,
        "divergence_ok": result["langkah_ke"] in case["accepted_divergence"],
        "determinable_ok": result["dapat_ditentukan"] is case["dapat_ditentukan"],
        "clean": not result["issues"],
    }


def summarize(runs: list[dict]) -> None:
    done = [r for r in runs if "result" in r]
    print(f"\nBerhasil {len(done)} dari {len(runs)} panggilan")
    for name in ("divergence_ok", "determinable_ok", "clean"):
        print(f"{name}: {sum(r[name] for r in done)}/{len(done)}")
    print("\nKasus dengan hasil di luar harapan:")
    for r in sorted(runs, key=lambda r: (r["id"], r["repeat"])):
        if "error" in r:
            print(f"  {r['id']} [{r['repeat']}] ERROR {r['error']}")
        elif not (r["divergence_ok"] and r["determinable_ok"] and r["clean"]):
            result = r["result"]
            print(f"  {r['id']} [{r['repeat']}] langkah_ke={result['langkah_ke']} dapat={result['dapat_ditentukan']} issues={result['issues']}")
            print(f"      {result['keterangan']}")


if __name__ == "__main__":
    jobs = [(case, repeat) for case in CASES for repeat in range(1, REPEATS + 1)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        runs = list(pool.map(lambda job: run_case(*job), jobs))
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8")
    summarize(runs)
