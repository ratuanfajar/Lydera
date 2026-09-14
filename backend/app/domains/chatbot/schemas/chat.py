from datetime import datetime

from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    classroom_id: int


class ChatSessionResponse(BaseModel):
    id: int
    classroom_id: int


class ChatAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class SourceCitation(BaseModel):
    source_type: str  # modul | oer | wolfram_alpha | web
    label: str
    reference: str
    trust_tier: int | None = None
    evidence: str
    justification: str
    verified: bool


class ChatAnswerResponse(BaseModel):
    status: str  # out_of_scope | answered
    message: str
    sources: list[SourceCitation] | None = None
    scope_klass: str


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
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
