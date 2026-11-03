from pydantic import BaseModel, model_validator


class BlockEditRequest(BaseModel):
    readable_text: str | None = None
    source_markup: str | None = None
    tabel: dict | None = None

    @model_validator(mode="after")
    def at_least_one(self):
        if self.readable_text is None and self.source_markup is None and self.tabel is None:
            raise ValueError("kirim minimal satu: readable_text, source_markup, atau tabel")
        return self


class BlockEditResponse(BaseModel):
    block_id: int
    block_type: str
    readable_text: str
    source_markup: str | None = None
    ringkasan: str | None = None
    tabel: dict | None = None
    review_priority: str
    issues: list[str] = []
