from pydantic import BaseModel, ConfigDict, Field

from app.domains.quizz.schemas.soal_response import SoalOpsiResponse


class SoalSubmitRequest(BaseModel):
    selected_option: str = Field(pattern="^[A-D]$")
    # langkah: list[str] | None = []

class SoalJawabanLangkahResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:int
    urutan:int
    teks:str

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
    options: list[SoalOpsiResponse]
    justification: SoalJustification | None
    langkah: list[SoalJawabanLangkahResponse]
