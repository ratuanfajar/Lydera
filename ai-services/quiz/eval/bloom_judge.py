import json
import statistics
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

AI_SERVICES = Path(r"E:\Lydera\ai-services")
sys.path.insert(0, str(AI_SERVICES))

from annotation import llm
from quiz.segment import build_segments

EVAL_DIR = AI_SERVICES / "chatbot" / "eval"
OUT_DIR = Path(__file__).parent

JUDGES = ["grok-4.3", "DeepSeek-V3.2", "Llama-3.3-70B-Instruct"]

JUDGE_SYSTEM = """# Peran
Anda mengklasifikasikan level kognitif Taksonomi Bloom (Anderson & Krathwohl) yang DITUNTUT oleh
sebuah soal matematika, HANYA berdasarkan soal itu sendiri -- bukan berdasarkan sulit-tidaknya
topik matematikanya. Skala yang dipakai cuma C1-C5 (C6/mencipta tidak dipakai -- MCQ 4 opsi tetap
tidak bisa menguji "create" murni).

# Level Kognitif
- C1 mengingat: soal cuma minta definisi/istilah/fakta langsung, tanpa kasus baru yang diproses.
- C2 memahami: soal minta menjelaskan/memparafrase konsep, atau mengenali contoh benar/salah dari
  suatu konsep -- tanpa menghitung/menerapkan prosedur ke kasus baru.
- C3 menerapkan: ada kasus/angka baru, siswa menerapkan SATU prosedur/rumus dari materi secara
  langsung untuk menyelesaikannya.
- C4 menganalisis: SATU klaim/pernyataan/proses disodorkan (dari satu tokoh/satu rangkaian
  penyelesaian), siswa menelusuri struktur internalnya untuk menemukan DI MANA/KENAPA letak
  kekeliruan atau hubungan sebab-akibatnya. Opsi jawaban adalah beberapa DIAGNOSIS berbeda atas
  SATU hal yang sama (mis. "keliru karena X", "keliru karena Y", "benar karena Z") -- bukan
  perbandingan beberapa hal yang terpisah.
- C5 mengevaluasi: BEBERAPA pendekatan/klaim/strategi TERPISAH (lebih dari satu skenario/solusi
  lengkap yang berdiri sendiri-sendiri) disodorkan berdampingan, siswa MEMBANDINGKAN semuanya dan
  menilai mana yang paling valid/efisien berdasarkan kriteria.

# Pembeda Kunci C4 vs C5
C4: HANYA SATU klaim/proses yang didiagnosis -- opsi jawaban semuanya tentang klaim/hal yang sama
itu. C5: ADA BEBERAPA klaim/pendekatan BERBEDA yang dibandingkan satu sama lain -- opsi jawaban
merujuk ke pendekatan-pendekatan yang berlainan, bukan satu hal yang sama.

# Output
Keluarkan HANYA JSON: {"level": 1-5}"""


def question_text_for_judge(soal: dict) -> str:
    parts = []
    stimulus = (soal.get("stimulus") or {}).get("readable_text", "")
    if stimulus:
        parts.append(f"Stimulus: {stimulus}")
    parts.append(f"Soal: {soal['question_text']}")
    opsi = "\n".join(f"{k}. {v}" for k, v in soal["options"].items())
    parts.append(opsi)
    return "\n\n".join(parts)


def judge_level(soal: dict, model: str) -> int:
    user = question_text_for_judge(soal)
    try:
        result = llm.complete_json(JUDGE_SYSTEM, user, model=model, max_tokens=100,
                                    required_keys=["level"], effort="low")
        level = int(result["level"])
        return level if 1 <= level <= 5 else 3
    except Exception:
        return 3


def majority(levels: list[int]) -> int:
    counts = {}
    for lv in levels:
        counts[lv] = counts.get(lv, 0) + 1
    best = max(counts.values())
    winners = [lv for lv, c in counts.items() if c == best]
    if len(winners) == 1:
        return winners[0]
    return int(statistics.median(levels))


def load_segments():
    segs = {}
    for bab, chapter_id in [("bab1", 1), ("bab2", 2)]:
        blocks = json.loads((EVAL_DIR / "blocks" / f"{bab}.json").read_text(encoding="utf-8"))
        segs[bab] = build_segments(chapter_id, blocks)
    return segs


def match_segment(soal: dict, segments: list) -> str:
    for seg in segments:
        if seg.reading_order_start <= soal["reading_order_start"] <= seg.reading_order_end:
            return seg.title
    return "?"


def main():
    samples = json.loads((OUT_DIR / "generated_soal.json").read_text(encoding="utf-8"))
    segments_by_bab = load_segments()

    rows = []
    for bab, items in samples.items():
        for item in items:
            soal = item["soal"]
            votes = {m: judge_level(soal, m) for m in JUDGES}
            voted = majority(list(votes.values()))
            seg_title = match_segment(soal, segments_by_bab[bab])
            rows.append({
                "bab": bab, "segment": seg_title, "intended": soal["bloom_level"],
                "votes": votes, "voted": voted, "exact_match": voted == soal["bloom_level"],
                "question": soal["question_text"][:60],
            })
            print(f"{bab} | {seg_title[:30]:30} | intended=C{soal['bloom_level']} voted=C{voted} "
                  f"votes={votes} match={voted == soal['bloom_level']}")

    (OUT_DIR / "judge_results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    exact_acc = sum(r["exact_match"] for r in rows) / len(rows)
    print(f"\nExact Match Accuracy keseluruhan: {exact_acc:.3f} ({sum(r['exact_match'] for r in rows)}/{len(rows)})")

    print("\nPer segmen (Jaccard / Hamming):")
    for bab, items in samples.items():
        for seg_title in dict.fromkeys(r["segment"] for r in rows if r["bab"] == bab):
            seg_rows = [r for r in rows if r["bab"] == bab and r["segment"] == seg_title]
            expected = set(r["intended"] for r in seg_rows)
            actual = set(r["voted"] for r in seg_rows)
            jaccard = len(expected & actual) / len(expected | actual)
            hamming = sum(1 for lv in range(1, 6) if (lv in expected) == (lv in actual)) / 5
            print(f"  {bab} / {seg_title[:35]:35} expected={sorted(expected)} actual={sorted(actual)} "
                  f"jaccard={jaccard:.3f} hamming={hamming:.3f}")


if __name__ == "__main__":
    main()
