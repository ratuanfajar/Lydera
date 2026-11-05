from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert

from app.core.db import AsyncSession
from app.domains.contents.models.record_note import RecordNote
from app.domains.contents.repositories.interfaces.note_interface import (
    NoteRepositoryInterface,
)
from app.domains.contents.schemas.record_note.record_note_create import RecordNoteCreate


class NoteRepository(NoteRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_note_by_chapter_id(self, chapter_id: int, student_id: int) -> Optional[RecordNote]:
        stmt = select(RecordNote).where(
            and_(
                RecordNote.student_id == student_id,
                RecordNote.chapter_id == chapter_id
            )
        )
        result = await self.db.scalar(stmt)
        return result

    async def save_note(self, student_id: int, record_note_create: RecordNoteCreate) -> RecordNote:
        stmt = (
            insert(RecordNote)
            .values(
                title=record_note_create.title, content=record_note_create.content, student_id=student_id, chapter_id=record_note_create.chapter_id,
            )
            .on_conflict_do_update(
                index_elements=["student_id", "chapter_id", ], set_={"title": record_note_create.title, "content": record_note_create.content},
            )
            .returning(RecordNote)
            .execution_options(populate_existing=True)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()
