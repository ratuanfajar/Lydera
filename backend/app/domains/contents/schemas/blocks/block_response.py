from pydantic import BaseModel, ConfigDict, computed_field
from app.core.config import settings

class BlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    reading_order: int
    block_type: str
    readable_text: str
    previous_text: str | None = None
    review_priority: str
    heading_level: int | None
    source_markup: str | None
    caption: str | None
    image_file: str | None

    @computed_field
    @property
    def image_url(self) -> str | None:
        if not self.image_filename:
            return None
        return f"{settings.BASE_URL}/static/annotations/{self.id}/raw-{self.id}/auto/images/{self.image_filename}"
