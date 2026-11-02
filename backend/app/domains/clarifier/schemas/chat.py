from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatSessionCreate(BaseModel):
    classroom_id: int

class ChatSessionQuery(BaseModel):
    classroom_id: int


class ChatSessionResponse(BaseModel):
    id: int
    classroom_id: int

class ChatSessionResponseWithMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    classroom_id: int
    first_message: str | None


class ChatAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class SourceCitation(BaseModel):
    source_type: str  # modul | oer
    label: str
    reference: str
    evidence: str
    justification: str
    verified: bool


class ChatAnswerResponse(BaseModel):
    status: str  # out_of_scope | answered
    message: str
    message_markup: str | None = None
    sources: list[SourceCitation] | None = None
    suggested_questions: list[str] | None = None
    scope_klass: str


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    content_markup: str | None = None
    citations: list[SourceCitation] | None = None
    created_at: datetime


class ReindexResponse(BaseModel):
    chapter_id: int
    kb_version: int
    chunks_indexed: int


class ReindexQueuedResponse(BaseModel):
    chapter_id: int
    status: str


class ReindexClassroomQueuedResponse(BaseModel):
    classroom_id: int
    status: str
