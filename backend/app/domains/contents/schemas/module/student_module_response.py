from pydantic import ConfigDict, Field

from app.domains.contents.schemas.module.module_progress_response import ModuleProgressResponse
from app.domains.contents.schemas.module.module_response import ModuleResponse
from app.domains.contents.schemas.chapters.student_chapter_detail_response import StudentChapterDetailResponse

class StudentModuleResponse(ModuleResponse):
    model_config = ConfigDict(from_attributes=True)
    
    progress: ModuleProgressResponse | None = Field(
        default=None, 
        validation_alias="module_progress"
    )

    chapters: list[StudentChapterDetailResponse]

    