import asyncio
import json
import traceback

from redis.asyncio import Redis

from app.core.taskiq import broker
from app.core.db import AsyncSessionLocal
from app.domains.quizz.repositories.repository import QuizRepository

from app.utils import paths
from app.domains.quizz.schemas.quiz_request_teacher_response import QuizRequestQuestionResponse
from app.domains.quizz.schemas.soal_create_request import SoalCreateRequest, SoalDataCreateRequest, StimulusCreateRequest
paths.setup()

from app.core.redis import get_redis_client
import quiz_pipeline


TTL_3_MINUTES = 180


@broker.task
async def process_quiz_request_task(quiz_request_id: int, idem_key: str) -> None:
    redis: Redis = await get_redis_client()
    channel_key = f"quiz_stream:{quiz_request_id}"
    result_key = f"quiz_result:{quiz_request_id}"
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

            # 3. Generate questions via LLM pipeline
            items_to_save: list[SoalCreateRequest] = []

            for link in chapter_links:
                blocks = await repo.get_blocks_for_chapter(link.chapter_id)
                blocks_as_rows = [
                    {
                        "reading_order": b.reading_order,
                        "block_type": b.block_type,
                        "readable_text": b.readable_text,
                    }
                    for b in blocks
                ]

                computed = await asyncio.to_thread(
                    quiz_pipeline.compute_for_chapter,
                    link.chapter_id,
                    blocks_as_rows,
                    link.hots_count,
                    link.lots_count,
                    on_progress=on_question_completed,
                )

                for data, result in computed:
                    review_priority = "normal" if result["matches"] else "high"
                    validation_notes = None
                    if not result["matches"]:
                        validation_notes = (
                            f"Validasi independen sampai ke jawaban {result['derived_option']}, berbeda dari "
                            f"jawaban Generation ({data['correct_option']}). Langkah validasi: "
                            f"{'; '.join(result['derived_langkah'])}"
                        )

                    stimulus_payload = None
                    if data.get("stimulus"):
                        stim_raw = data["stimulus"]
                        stimulus_payload = StimulusCreateRequest(
                            source_markup=stim_raw.get("source_markup", ""),
                            readable_text=stim_raw.get("readable_text", ""),
                            source_reading_order_start=stim_raw.get("source_reading_order_start"),
                            source_reading_order_end=stim_raw.get("source_reading_order_end"),
                        )

                    data_payload = SoalDataCreateRequest(
                        bloom_level=data.get("bloom_level", 3),
                        question_text=data["question_text"],
                        correct_option=data["correct_option"],
                        options=data.get("options", {}),
                        langkah=data.get("langkah", []),
                        kesimpulan=data.get("kesimpulan", ""),
                        reading_order_start=data.get("reading_order_start", 0),
                        reading_order_end=data.get("reading_order_end", 0),
                        stimulus=stimulus_payload,
                    )

                    items_to_save.append(
                        SoalCreateRequest(
                            chapter_id=link.chapter_id,
                            data=data_payload,
                            review_priority=review_priority,
                            validation_notes=validation_notes,
                        )
                    )

            # 4. Save to Database using existing QuizRepository method
            saved = await repo.save_quiz_data(
                quiz_request_id=quiz_request_id,
                classroom_id=quiz_request.classroom_id,
                status_val="done",
                items=items_to_save,
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
            await redis.set(idem_key, done_meta, ex=TTL_3_MINUTES)
            await redis.expire(map_key, TTL_3_MINUTES)

            # 7. Broadcast completion stream
            done_payload = {
                "quiz_request_id": quiz_request_id,
                "status": "done",
                "completed": total_questions,
                "total": total_questions,
                "message": f"Berhasil membuat dan menyimpan {len(serialized_questions)} soal.",
                "data": serialized_questions,
            }
            await redis.publish(channel_key, json.dumps(done_payload))

        except Exception as exc:
            traceback.print_exc()
            await db.rollback()

            await repo.update_quiz_request_status_by_id(quiz_request_id, "failed", error=str(exc))
            await db.commit()

            failed_meta = json.dumps({"quiz_request_id": quiz_request_id, "status": "failed"})
            await redis.set(idem_key, failed_meta, ex=TTL_3_MINUTES)

            await redis.publish(
                channel_key,
                json.dumps({
                    "quiz_request_id": quiz_request_id,
                    "status": "failed",
                    "error": str(exc),
                }),
            )