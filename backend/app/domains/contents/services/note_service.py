from typing import Optional

from app.core.db import AsyncSession
from app.domains.contents.models.record_note import RecordNote
from app.domains.contents.repositories.interfaces.content_interface import (
    ContentRepositoryInterface,
)
from app.domains.contents.schemas.record_note.record_note_create import RecordNoteCreate
from app.domains.contents.schemas.record_note.record_note_response import RecordNoteResponse


class RecordNoteService:
    def __init__(self, repo: ContentRepositoryInterface, db: AsyncSession):
        self.repo = repo
        self.db = db

    async def get_record_note(
        self,
        chapter_id: int,
        student_id: int,
    ) -> Optional[RecordNoteResponse]:
        result: RecordNote | None = await self.repo.get_note_by_chapter_id(
            chapter_id,
            student_id,
        )

        if result is None:
            return None

        return RecordNoteResponse.model_validate(result)

    async def save_record_note(
        self,
        dto: RecordNoteCreate,
        student_id: int,
    ) -> RecordNoteResponse:
        result = await self.repo.save_note(student_id, dto)
        await self.db.commit()
        return RecordNoteResponse.model_validate(result)
