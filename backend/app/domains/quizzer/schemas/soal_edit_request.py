from pydantic import BaseModel, Field, field_validator, model_validator

OPTION_LABELS = {"A", "B", "C", "D"}
MIN_FEEDBACK_CHARS = 3
MARKUP_KEYS = {"question", "options", "langkah", "kesimpulan"}


class SoalEditRequest(BaseModel):
    question_text: str | None = None
    options: dict[str, str] | None = None
    correct_option: str | None = Field(default=None, pattern="^[A-D]$")
    langkah: list[str] | None = None
    kesimpulan: str | None = None
    markup: dict | None = None

    @field_validator("markup")
    @classmethod
    def markup_keys(cls, value):
        if value is None:
            return value
        if not set(value) <= MARKUP_KEYS:
            raise ValueError("markup hanya boleh berisi question, options, langkah, kesimpulan")
        if "options" in value and (not isinstance(value["options"], dict) or set(value["options"]) != OPTION_LABELS):
            raise ValueError("markup.options harus tepat berisi A, B, C, dan D")
        if "langkah" in value and not (isinstance(value["langkah"], list) and all(isinstance(x, str) for x in value["langkah"])):
            raise ValueError("markup.langkah harus berupa daftar teks")
        for key in ("question", "kesimpulan"):
            if key in value and not (isinstance(value[key], str) and value[key].strip()):
                raise ValueError(f"markup.{key} harus berupa teks tidak kosong")
        if "options" in value and not all(isinstance(text, str) and text.strip() for text in value["options"].values()):
            raise ValueError("markup.options harus berupa teks tidak kosong")
        if "langkah" in value and not all(text.strip() for text in value["langkah"]):
            raise ValueError("markup.langkah tidak boleh berisi teks kosong")
        return value

    @field_validator("options")
    @classmethod
    def options_must_be_a_to_d(cls, value):
        if value is not None and (set(value) != OPTION_LABELS or not all(text.strip() for text in value.values())):
            raise ValueError("options harus tepat berisi A, B, C, dan D dengan teks tidak kosong")
        return value


class StimulusEditRequest(BaseModel):
    source_markup: str | None = None
    narasi: str | None = None
    spesifikasi: dict | None = None

    @model_validator(mode="after")
    def exactly_one_form(self):
        if (self.source_markup is None) == (self.spesifikasi is None):
            raise ValueError("kirim tepat satu: source_markup (stimulus teks) atau spesifikasi (stimulus bertipe)")
        if self.source_markup is not None and self.narasi is not None:
            raise ValueError("narasi hanya untuk stimulus bertipe (bersama spesifikasi)")
        return self


class SoalRegenerateRequest(BaseModel):
    feedback: str = Field(min_length=3, max_length=2000)

    @field_validator("feedback")
    @classmethod
    def feedback_must_have_content(cls, value):
        value = value.strip()
        if len(value) < MIN_FEEDBACK_CHARS:
            raise ValueError(f"feedback minimal {MIN_FEEDBACK_CHARS} karakter")
        return value


class SoalStatusResponse(BaseModel):
    id: int
    review_status: str
