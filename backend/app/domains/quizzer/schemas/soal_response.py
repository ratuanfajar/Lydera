from pydantic import BaseModel


class SoalOpsiResponse(BaseModel):
    label: str
    opsi_text: str


class SoalResponse(BaseModel):
    id: int
    chapter_id: int
    stimulus_id: int | None
    bloom_level: int
    question_text: str
    options: list[SoalOpsiResponse]
    correct_option: str
    langkah: list[str]
    kesimpulan: str
    stimulus_text: str | None
    review_status: str
    review_priority: str
    validation_notes: str | None
