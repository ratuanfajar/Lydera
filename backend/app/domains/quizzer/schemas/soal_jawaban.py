from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class SoalSubmitRequest(BaseModel):
    selected_option: str = Field(pattern="^[A-D]$")
    langkah: list[Annotated[str, Field(max_length=1000)]] | None = Field(default_factory=list, max_length=30)

class SoalJawabanLangkahResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:int
    urutan:int
    teks:str

class SoalSubmitResponse(BaseModel):
    soal_id: int
    status: str


class JustificationPoint(BaseModel):
    point: str
    step_ref: int | None = None
    is_divergence: bool = False


class SoalJustification(BaseModel):
    divergence_step: int | None
    error_type: str | None = None
    diagnosis: str
    points: list[JustificationPoint] = []
    personalized_justification: str
    perlu_ditinjau: bool = False


class QuizResultItem(BaseModel):
    soal_id: int
    question_text: str
    selected_option: str | None
    correct_option: str
    kesimpulan: str
    langkah_kunci: list[str]
    is_correct: bool | None
    justification: SoalJustification | None
    evaluasi_gagal: bool = False
    evaluasi_diproses: bool = False
    langkah: list[SoalJawabanLangkahResponse]
