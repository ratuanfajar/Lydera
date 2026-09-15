from pydantic import BaseModel, Field


class SoalSubmitRequest(BaseModel):
    selected_option: str = Field(pattern="^[A-D]$")
    langkah: list[str] | None = []


class SoalSubmitResponse(BaseModel):
    soal_id: int
    status: str


class SoalJustification(BaseModel):
    divergence_step: int | None
    diagnosis: str
    personalized_justification: str


class QuizResultItem(BaseModel):
    soal_id: int
    question_text: str
    selected_option: str | None
    correct_option: str
    is_correct: bool | None
    justification: SoalJustification | None
