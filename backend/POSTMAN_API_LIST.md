# Lydera Backend API — for Postman Collection Import

Base URL: `{{base_url}}/api` (example: `http://localhost:8000/api`)

Auth: Bearer JWT in header `Authorization: Bearer <token>`, obtained from `POST /users/login`. Roles: `student`, `teacher`, `admin`.

Response envelope (success): `{ "message": string, "data": T }`
Response envelope (error): `{ "detail": string, "errors": array|null }`

Common error codes on any protected endpoint: `401` (missing/invalid token), `403` (wrong role), `422` (validation failed, `errors[]` populated).

---

## Users / Auth

1. **POST /users/login** — public. Body: `{ "email": string, "password": string, "role": "student"|"teacher" }`. Returns `data: "<jwt>"`. 401 on bad credentials.
2. **GET /users/profile** — auth (any role). No body. Returns `{ id, email, teacher: {id,created_at,updated_at}|null, student: {id,nis,nisn,grade,created_at,updated_at}|null }`.
3. **POST /teachers** — public register. Body: `{ email, password (min 8), confirm_password (min 8), role: "teacher" }`. Returns `TeacherResponse`.
4. **POST /students** — public register. Body: `{ email, password, confirm_password, role: "student" }`. Returns `StudentResponse`.
5. **GET /teachers/dashboard** — role teacher. Query: `classroom_id` (int, required), `limit` (int, optional). Returns `{ teacher_email, classroom_info, total_modules, total_exams, total_students, newest_modules, newest_exams }`.
6. **GET /teachers/modules** — role teacher. Query: `classroom_id` (required), `search` (optional), `status` (`Semua`|`Draft`|`Publish`, default `Semua`). Returns list of module+chapters.
7. **GET /teachers/modules/{module_id}** — role teacher. Query: `classroom_id` (required). Returns single module detail.
8. **GET /teachers/chapters/{chapter_id}** — role teacher. Returns chapter + `blocks[]`.
9. **GET /students/dashboard** — role student. Query: `classroom_id` (required). Returns `{ student_email, classroom_info, modules_not_done, exam_not_done }`.
10. **GET /students/dashboard/tasks** — role student. Query: `classroom_id` (required), `status` (`Semua`|`Materi`|`Soal Ujian`, default `Semua`). Returns `{ modules[], exams[] }`.
11. **GET /students/modules** — role student. Query: `classroom_id` (required), `status` (`Semua`|`Belum Selesai`|`Selesai`, required). Returns list of module+progress.
12. **GET /students/modules/{module_id}** — role student. Query: `classroom_id` (required). Returns module + progress + chapters.
13. **POST /students/chapters/{chapter_id}/start** — role student. No body. Returns chapter detail + progress + blocks.
14. **POST /students/chapters/{chapter_id}/mark-complete** — role student. No body. Returns `data: true`.

## Cities

15. **GET /cities** — role teacher. Returns `[{id,name,created_at,updated_at}]`.
16. **POST /cities** — role admin. Body: `{ "name": string(1-255) }`. Returns created city.

## Schools

17. **POST /schools** — role admin. Body: `{ "name": string(1-255), "city_id": int }`. Returns created school.
18. **GET /schools/{school_id}** — role teacher. Returns `{id,city_id,name,created_at,updated_at}`.
19. **GET /schools/city/{city_id}** — role teacher. Returns list of schools.

## Classrooms

20. **POST /classrooms** — role teacher. Body: `{ "name": string(1-100), "classroom_type_id": int, "school_id": int, "grade": 10|11|12 }`. Returns created classroom (includes generated `code`).
21. **GET /classrooms** — role teacher or student. Returns classrooms of the logged-in user.
22. **GET /classrooms/{classroom_id}** — role teacher or student. Returns single classroom.
23. **POST /classrooms/join** — role student. Body: `{ "code": string(7 chars) }`. Returns `data: true`.
24. **GET /classroom-types** — public. Returns `[{id,name,created_at,updated_at}]`.

## Fases

25. **GET /fases** — role teacher. Returns `[{id, kode}]`.

## Modules

26. **POST /modules** — role teacher. Body: `{ "title": string, "description": string, "fase_id": int, "classroom_id": int, "status": "draft"|"publish" (optional, default draft) }`. Returns created module.
27. **POST /modules/publish/{module_id}** — role teacher. No body. Returns `data: true`.

## Chapters

28. **POST /chapters** — role teacher. `multipart/form-data`: `module_id`(int), `title`(string), `cp_id`(int), `number`(int, optional), `file`(PDF, required). Triggers async MinerU annotation pipeline. Returns `{ chapter_id, job_id, status: "queued" }`. 409 if output dir already has data.
29. **GET /chapters/jobs/{job_id}/stream** — SSE (`text/event-stream`) of MinerU job progress via Redis pub/sub. Events: `{job_id, status, progress, message}`. Ends on `status: done|failed`.
30. **GET /chapters/preview** — role teacher. Query: `annotation_path` (string, e.g. `16/raw-16/auto/annotated.json`). Returns list of block previews before DB commit.
31. **POST /chapters/confirm/{chapter_id}** — role teacher. Body: `{ "annotation_path": string }`. Ingests annotated JSON into DB. Returns `data: <int>` (blocks inserted).

## Blocks

32. **POST /blocks/{block_id}/regenerate** — no explicit role check on route (teacher use). Body: `{ "feedback": string }`. Regenerates block readable text via LLM. Returns `{ block_id, readable_text }`. 404 if block not found.

## Quiz Requests

33. **POST /quiz-requests** — role teacher. Body:
    ```json
    { "module_id": int, "chapters": [{ "chapter_id": int, "hots_count": int, "lots_count": int }] }
    ```
    Enqueues async per-chapter LLM quiz generation. Returns `{ quiz_request_id, status: "queued" }`.
34. **GET /quiz-requests/{quiz_request_id}/status** — Returns `{ quiz_request_id, status: "queued"|"running"|"done"|"failed", error: string|null }`.
35. **GET /quiz-requests/{quiz_request_id}/soal** — Returns list of `Soal` objects generated so far (raw, teacher-facing — no student answers).
36. **GET /quiz-requests/{quiz_request_id}/my-results** — role student. Hasil kuis siswa yang login: untuk tiap soal, jawaban yang dipilih + `is_correct`; untuk yang salah, `justification` (dievaluasi via LLM saat pertama diminta, lalu disimpan — panggilan berikutnya pakai hasil tersimpan, bukan panggil LLM ulang). Response:
    ```json
    [{
      "soal_id": int, "question_text": string, "selected_option": string|null,
      "correct_option": string, "is_correct": bool|null,
      "justification": { "divergence_step": int|null, "diagnosis": string, "personalized_justification": string } | null
    }]
    ```
    `selected_option`/`is_correct`/`justification` are `null` if the student hasn't answered that soal yet.

## Soal

Soal shape:
```json
{
  "id": int, "chapter_id": int, "stimulus_id": int|null, "bloom_level": int,
  "question_text": string, "options": [{"label": string, "opsi_text": string}],
  "correct_option": string, "langkah": [string], "kesimpulan": string,
  "stimulus_text": string|null, "review_status": string, "review_priority": string,
  "validation_notes": string|null
}
```

37. **GET /soal/{soal_id}** — Returns single soal.
38. **POST /soal/{soal_id}/submit** — role student. Body: `{ "selected_option": "A"|"B"|"C"|"D", "langkah": [string] }` (langkah = student's own step-by-step working, scratchwork). Saves the answer — no LLM call here. Returns `{ soal_id, status: "saved" }`. 400 if this student already answered this soal (one submission per student per soal).
39. **PATCH /soal/{soal_id}** — role teacher. Only for standalone soal (`stimulus_id` null, typically LOTS). Body (all optional): `{ question_text?, options?: {label:text}, correct_option?, langkah?: [string], kesimpulan? }`. Returns updated soal.
40. **POST /soal/{soal_id}/approve** — role teacher. Returns `{ id, review_status: "approved" }`.
41. **POST /soal/{soal_id}/reject** — role teacher. Returns `{ id, review_status: "rejected" }`.
42. **POST /soal/{soal_id}/regenerate** — role teacher. Only for HOTS soal (has `stimulus_id`). Body: `{ "feedback": string }`. Edits the critiqued soal based on its old content (not a from-scratch regenerate). If the fix only concerns that soal, only it changes. If it actually requires changing the shared stimulus, the stimulus is updated too and every soal sharing it gets re-checked for consistency — but only the ones whose content actually needed adjusting are touched/saved; unaffected sibling soal stay untouched. 400 if no stimulus. Returns the full cluster `Soal[]` (touched and untouched soal alike).

## Misc

43. **GET /health** — public. Returns `{ message: "Sehat", data: true }`.
