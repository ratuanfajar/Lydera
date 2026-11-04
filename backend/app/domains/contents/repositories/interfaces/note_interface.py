from abc import ABC, abstractmethod
from typing import Optional

from app.domains.contents.models.record_note import RecordNote
from app.domains.contents.schemas.record_note.record_note_create import RecordNoteCreate


class NoteRepositoryInterface(ABC):
    @abstractmethod
    async def get_note_by_chapter_id(self, chapter_id: int, student_id: int) -> Optional[RecordNote]: raise NotImplementedError

    @abstractmethod
    async def save_note(self, student_id: int, record_note_create: RecordNoteCreate) -> RecordNote: raise NotImplementedError
