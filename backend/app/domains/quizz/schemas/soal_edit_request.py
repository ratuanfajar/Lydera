from pydantic import BaseModel


class SoalEditRequest(BaseModel):
    question_text: str | None = None
    options: dict[str, str] | None = None
    correct_option: str | None = None
    langkah: list[str] | None = None
    kesimpulan: str | None = None


class SoalRegenerateRequest(BaseModel):
    feedback: str


class SoalStatusResponse(BaseModel):
    id: int
    review_status: str
