from pydantic import BaseModel, ConfigDict


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chapter_id: int
    pdf_path: str
    # out_dir: str
    status: str
    error: str | None
    blocks_total: int | None

    