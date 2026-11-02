import asyncio
import json
import traceback

from redis.asyncio import Redis

from app.core.taskiq import broker
from app.core.db import AsyncSessionLocal
from app.domains.quizzer.repositories.repository import QuizRepository

from app.utils import paths
from app.domains.quizzer.schemas.quiz_request_teacher_response import QuizRequestQuestionResponse
from app.domains.quizzer.schemas.soal_create_request import SoalCreateRequest, SoalDataCreateRequest, StimulusCreateRequest
paths.setup()

from app.core.redis import get_redis_client
from quizzer import quizzer_pipeline


TTL_3_MINUTES = 180
KEEP_ALIVE_SECONDS = 60
GENERIC_FAILURE_MESSAGE = "Pembuatan kuis gagal. Coba lagi beberapa saat lagi."


class QuizGenerationError(Exception):
    pass


def _to_soal_create_request(item: dict) -> SoalCreateRequest:
    data = item["data"]
    stimulus = None
    if data.get("stimulus"):
        stim_raw = data["stimulus"]
        stimulus = StimulusCreateRequest(
            source_markup=stim_raw.get("source_markup", ""),
            readable_text=stim_raw.get("readable_text", ""),
            ringkasan=stim_raw.get("ringkasan"),
            tabel=stim_raw.get("tabel"),
            source_reading_order_start=stim_raw.get("source_reading_order_start"),
            source_reading_order_end=stim_raw.get("source_reading_order_end"),
        )
    return SoalCreateRequest(
        chapter_id=item["chapter_id"],
        data=SoalDataCreateRequest(
            bloom_level=data.get("bloom_level", 3),
            question_text=data["question_text"],
            correct_option=data["correct_option"],
            options=data.get("options", {}),
            langkah=data.get("langkah", []),
            kesimpulan=data.get("kesimpulan", ""),
            reading_order_start=data.get("reading_order_start", 0),
            reading_order_end=data.get("reading_order_end", 0),
            stimulus=stimulus,
            markup=data.get("markup"),
        ),
        review_priority=item["review_priority"],
        validation_notes=item["validation_notes"],
        source_point=item["source_point"],
    )


def _failure_summary(report: dict) -> str:
    reasons = []
    for chapter in report["chapters"]:
        if chapter["skipped_reason"]:
            reasons.append(f"Bab {chapter['chapter_id']}: {chapter['skipped_reason']}")
        reasons.extend(f"Bab {chapter['chapter_id']} level C{f['level']}: {f['error']}" for f in chapter["failed"][:3])
    return " ".join(reasons)[:1000]


def _done_message(saved: int, report: dict) -> str:
    failed = report["summary"]["failed"]
    skipped = sum(1 for chapter in report["chapters"] if chapter["skipped_reason"])
    notes = [f"{failed} soal gagal dibuat" if failed else "", f"{skipped} bab dilewati" if skipped else ""]
    message = f"Berhasil membuat dan menyimpan {saved} soal."
    notes = ", ".join(note for note in notes if note)
    return f"{message} {notes}; lihat laporan cakupan." if notes else message


def _mark_conversion_failure(report: dict, item: dict) -> None:
    chapter = next(c for c in report["chapters"] if c["chapter_id"] == item["chapter_id"])
    group = "lots" if item["level"] <= 3 else "hots"
    chapter["generated"][group] -= 1
    chapter["failed"].append({"level": item["level"], "point": item["source_point"][:120], "error": "Data soal tidak dapat disimpan."})
    report["summary"]["generated"] -= 1
    report["summary"]["failed"] += 1


@broker.task
async def process_quiz_request_task(quiz_request_id: int, idem_key: str) -> None:
    redis: Redis = await get_redis_client()
    channel_key = f"quiz_stream:{quiz_request_id}"
    result_key = f"quiz_result:{quiz_request_id}"
    coverage_key = f"quiz_coverage:{quiz_request_id}"
    map_key = f"quiz_idem_map:{quiz_request_id}"
    loop = asyncio.get_running_loop()

    async with AsyncSessionLocal() as db:
        repo = QuizRepository(db)

        quiz_request = await repo.get_quiz_request(quiz_request_id)
        if quiz_request is None:
            return

        await repo.update_quiz_request_status(quiz_request, "running")
        await db.commit()

        await redis.set(
            idem_key,
            json.dumps({"quiz_request_id": quiz_request_id, "status": "running"}),
            ex=TTL_3_MINUTES,
        )
        await redis.expire(map_key, TTL_3_MINUTES)

        async def keep_alive() -> None:
            while True:
                await asyncio.sleep(KEEP_ALIVE_SECONDS)
                await redis.expire(idem_key, TTL_3_MINUTES)
                await redis.expire(map_key, TTL_3_MINUTES)

        keep_alive_task = asyncio.create_task(keep_alive())

        try:
            chapter_links = await repo.get_chapter_links(quiz_request_id)
            total_questions = sum(link.hots_count + link.lots_count for link in chapter_links)
            completed_questions = 0

            await redis.publish(
                channel_key,
                json.dumps({
                    "quiz_request_id": quiz_request_id,
                    "status": "running",
                    "completed": 0,
                    "total": total_questions,
                    "message": f"Memulai pembuatan {total_questions} soal...",
                }),
            )

            def on_question_completed():
                nonlocal completed_questions
                completed_questions += 1
                progress_payload = {
                    "quiz_request_id": quiz_request_id,
                    "status": "running",
                    "completed": completed_questions,
                    "total": total_questions,
                    "message": f"Soal {completed_questions}/{total_questions} selesai diproses",
                }
                asyncio.run_coroutine_threadsafe(
                    redis.publish(channel_key, json.dumps(progress_payload)),
                    loop,
                )

            # 3. Generate questions via LLM pipeline (semua bab diproses bersama)
            chapters_input = []
            for link in chapter_links:
                blocks = await repo.get_blocks_for_chapter(link.chapter_id)
                chapters_input.append({
                    "chapter_id": link.chapter_id,
                    "blocks": [
                        {
                            "reading_order": b.reading_order,
                            "block_type": b.block_type,
                            "readable_text": b.readable_text,
                        }
                        for b in blocks
                    ],
                    "cp_text": await repo.get_chapter_cp_text(link.chapter_id),
                    "hots_count": link.hots_count,
                    "lots_count": link.lots_count,
                })

            computed = await asyncio.to_thread(
                quizzer_pipeline.compute_for_quiz,
                chapters_input,
                on_progress=on_question_completed,
            )
            report = computed["report"]
            items_to_save: list[SoalCreateRequest] = []
            for item in computed["items"]:
                try:
                    items_to_save.append(_to_soal_create_request(item))
                except Exception:
                    traceback.print_exc()
                    _mark_conversion_failure(report, item)

            if not items_to_save:
                raise QuizGenerationError(f"Tidak ada soal yang berhasil dibuat. {_failure_summary(report)}")

            # 4. Save to Database using existing QuizRepository method
            saved = await repo.save_quiz_data(
                quiz_request_id=quiz_request_id,
                classroom_id=quiz_request.classroom_id,
                status_val="done",
                items=items_to_save,
                coverage_report=report,
            )

            if not saved:
                raise Exception(f"Gagal menyimpan quiz_request_id={quiz_request_id}")

            # 5. Load inserted records via repo and serialize with QuizRequestQuestionResponse
            saved_soals = await repo.get_soal_for_request(quiz_request_id)
            serialized_questions = [
                QuizRequestQuestionResponse.model_validate(soal).model_dump(mode="json")
                for soal in saved_soals
            ]

            # 6. Update Redis status & output payload
            done_meta = json.dumps({"quiz_request_id": quiz_request_id, "status": "done"})
            await redis.set(result_key, json.dumps(serialized_questions), ex=TTL_3_MINUTES)
            await redis.set(coverage_key, json.dumps(report), ex=TTL_3_MINUTES)
            await redis.set(idem_key, done_meta, ex=TTL_3_MINUTES)
            await redis.expire(map_key, TTL_3_MINUTES)

            # 7. Broadcast completion stream
            done_payload = {
                "quiz_request_id": quiz_request_id,
                "status": "done",
                "completed": total_questions,
                "total": total_questions,
                "message": _done_message(len(serialized_questions), report),
                "data": serialized_questions,
                "coverage_report": report,
            }
            await redis.publish(channel_key, json.dumps(done_payload))

        except Exception as exc:
            traceback.print_exc()
            await db.rollback()

            error_message = str(exc) if isinstance(exc, QuizGenerationError) else GENERIC_FAILURE_MESSAGE
            await repo.update_quiz_request_status_by_id(quiz_request_id, "failed", error=error_message)
            await db.commit()

            failed_meta = json.dumps({"quiz_request_id": quiz_request_id, "status": "failed"})
            await redis.set(idem_key, failed_meta, ex=TTL_3_MINUTES)

            await redis.publish(
                channel_key,
                json.dumps({
                    "quiz_request_id": quiz_request_id,
                    "status": "failed",
                    "error": error_message,
                }),
            )
        finally:
            keep_alive_task.cancel()