from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domains.quizzer.schemas.soal_response import SoalOpsiResponse

class SoalSubmitRequest(BaseModel):
    selected_option: str = Field(pattern="^[A-D]$")
    langkah: list[Annotated[str, Field(max_length=1000)]] | None = Field(default=None, max_length=30)

    @field_validator("langkah")
    @classmethod
    def drop_blank_steps(cls, value):
        return None if value is None else [step.strip() for step in value if step.strip()]

class SoalJawabanLangkahResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:int
    urutan:int
    teks:str

class SoalSubmitResponse(BaseModel):
    soal_id: int
    status: str


class LetakKesalahan(BaseModel):
    dapat_ditentukan: bool
    langkah_ke: int | None = None
    kutipan: str | None = None
    keterangan: str
    perlu_ditinjau: bool = False


class QuizResultItem(BaseModel):
    soal_id: int
    question_text: str
    selected_option: str | None
    correct_option: str
    kesimpulan: str
    langkah_kunci: list[str]
    is_correct: bool | None
    letak_kesalahan: LetakKesalahan | None
    evaluasi_gagal: bool = False
    evaluasi_diproses: bool = False
    langkah: list[SoalJawabanLangkahResponse]
    options: list[SoalOpsiResponse]
