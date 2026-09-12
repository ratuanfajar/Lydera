from pydantic import ConfigDict, Field

from app.domains.contents.schemas.module.module_progress_response import ModuleProgressResponse
from app.domains.contents.schemas.module.module_response import ModuleResponse
from app.domains.contents.schemas.chapters.student_chapter_detail_response import StudentChapterDetailResponse
from app.domains.contents.models.module import ModuleStatus
from app.domains.contents.schemas.chapters.chapter_response import ChapterResponse

class TeacherModuleResponse(ModuleResponse):
    model_config = ConfigDict(from_attributes=True)
    
    status: ModuleStatus | None = None
    
    chapters: list[ChapterResponse]