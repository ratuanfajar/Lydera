from pydantic import BaseModel, ConfigDict


class BlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reading_order: int
    block_type: str
    readable_text: str
    review_priority: str
    heading_level: int | None
    source_markup: str | None
    caption: str | None
    image_file: str | None
