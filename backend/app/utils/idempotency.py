import hashlib
import json
from redis.asyncio import Redis

def generate_idempotency_key(
    teacher_id: int, classroom_id: int, module_id: int, title: str, chapters: list[dict], 
    max_duration_minutes : int, max_retry : int,
    start_time : str,
    end_time : str
) -> str:
    sorted_chapters = sorted(chapters, key=lambda x: x["chapter_id"])
    payload = {
        "teacher_id": teacher_id,
        "classroom_id": classroom_id,
        "module_id": module_id,
        "title": title.strip().lower(),
        "chapters": sorted_chapters,
        "max_duration_minutes" : max_duration_minutes,
        "max_retry" : max_retry,
        "start_time" : start_time,
        "end_time" : end_time
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    hash_digest = hashlib.sha256(encoded).hexdigest()
    return f"quiz_idem:{hash_digest}"