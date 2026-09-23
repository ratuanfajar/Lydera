import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

AI_SERVICES = Path(r"E:\Lydera\ai-services")
sys.path.insert(0, str(AI_SERVICES))

from quiz.quiz_pipeline import compute_for_chapter

EVAL_DIR = AI_SERVICES / "chatbot" / "eval"
OUT_DIR = Path(__file__).parent


def run_chapter(chapter_id, blocks_path):
    blocks = json.loads(blocks_path.read_text(encoding="utf-8"))
    results = compute_for_chapter(chapter_id, blocks, hots_count=6, lots_count=6)
    return [{"soal": data, "validasi": validasi} for data, validasi in results]


bab1_soal = run_chapter(1, EVAL_DIR / "blocks" / "bab1.json")
print(f"bab1: {len(bab1_soal)} soal")
bab2_soal = run_chapter(2, EVAL_DIR / "blocks" / "bab2.json")
print(f"bab2: {len(bab2_soal)} soal")

out = {"bab1": bab1_soal, "bab2": bab2_soal}
out_path = OUT_DIR / "generated_soal.json"
out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"saved: {out_path}")

for label, items in out.items():
    print(f"\n{label}:")
    for item in items:
        d = item["soal"]
        v = item["validasi"]
        print(f"  bloom={d['bloom_level']} matches={v['matches']} | {d['question_text'][:70]}")
