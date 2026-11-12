from datetime import datetime
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from app.domains.jobs.schemas.job_response import JobResponse

class ChapterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    module_id: int
    number: int | None
    title: str | None
    source_file: str | None
    is_need_review: bool
    job: JobResponse | None = Field(
        default=None,
        validation_alias="latest_job",
    )
    cp_id: int | None
    created_at: datetime




