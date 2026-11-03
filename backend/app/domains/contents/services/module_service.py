from app.core.exceptions import ForbiddenException, NotFoundException
from app.domains.contents.repositories.interfaces.module_interface import ModuleRepositoryInterface
from app.domains.contents.schemas.module.student_module_request import StudentModuleRequest, StudentModuleStatus
from app.domains.contents.schemas.module.student_module_detail_request import StudentModuleDetailRequest
from app.domains.contents.schemas.module.student_module_response import StudentModuleResponse, StudentModuleWithoutChaptersResponse
from app.domains.contents.schemas.module.teacher_module_request import TeacherModuleRequest
from app.domains.contents.schemas.module.teacher_module_detail_request import TeacherModuleDetailRequest
from app.domains.contents.schemas.module.teacher_module_response import TeacherModuleResponse, TeacherModuleWithoutChapterResponse
from app.domains.jobs.repositories.interface import JobRepositoryInterface
from app.domains.contents.models import Module, ModuleStatus
from app.core.db import AsyncSession
from app.tasks.file_tasks import cleanup_module_files_task


class ModuleService:
    def __init__(self, repo: ModuleRepositoryInterface, job_repo: JobRepositoryInterface, db: AsyncSession):
        self.repo = repo
        self.job_repo = job_repo
        self.db = db

    async def create_module(self, title: str, description: str, status: ModuleStatus, classroom_id: int, teacher_id: int, fase_id: int | None) -> Module:
        module = await self.repo.create_module_teacher(title, description, status, classroom_id, teacher_id, fase_id)
        if not module:
            raise ForbiddenException(detail="Kelas tidak ditemukan atau Anda tidak memiliki akses.")
        try:
            await self.db.commit()
            await self.db.refresh(module)
            return module
        except Exception as e:
            await self.db.rollback()
            raise e

    async def publish_module(self, module_id: int, teacher_id: int) -> bool:
        return await self.repo.publish_module(module_id, teacher_id)

    async def delete_module(self, teacher_id: int, classroom_id: int, module_id: int) -> bool:
        file_paths = await self.job_repo.get_job_file_paths_by_module(
            module_id=module_id,
            classroom_id=classroom_id,
            teacher_id=teacher_id
        )

        deleted = await self.repo.delete_module_teacher(module_id, classroom_id, teacher_id)
        if not deleted:
            raise NotFoundException("Module tidak ditemukan.")
        await self.db.commit()

        if file_paths:
            await cleanup_module_files_task.kiq(file_paths)

        return True

    async def get_teacher_modules(self, dto: TeacherModuleRequest, teacher_id: int) -> list[TeacherModuleWithoutChapterResponse]:
        try:
            raw_modules = await self.repo.get_all_modules_teachers(dto.classroom_id, teacher_id, dto.status, dto.search)
            modules = [TeacherModuleWithoutChapterResponse.model_validate(m) for m in raw_modules]
            return modules
        except Exception as e:
            raise e

    async def get_teacher_module(self, dto: TeacherModuleDetailRequest, module_id: int, teacher_id: int) -> TeacherModuleResponse:
        try:
            raw_module = await self.repo.get_detail_module_teacher(module_id, dto.classroom_id, teacher_id)
            if not raw_module:
                raise ForbiddenException("Module tidak punya akses atau tidak ada")
            module = TeacherModuleResponse.model_validate(raw_module)
            return module
        except Exception as e:
            raise e

    async def get_student_modules(self, dto: StudentModuleRequest, student_id: int) -> list[StudentModuleWithoutChaptersResponse]:
        try:
            raw_modules = await self.repo.get_all_modules_student(dto.classroom_id, student_id, dto.status)
            modules = [StudentModuleWithoutChaptersResponse.model_validate(m) for m in raw_modules]
            return modules
        except Exception as e:
            raise e

    async def get_student_module(self, dto: StudentModuleDetailRequest, student_id: int, module_id: int) -> StudentModuleResponse:
        try:
            raw_module = await self.repo.get_detail_module_student(module_id, dto.classroom_id, student_id)
            if not raw_module:
                raise NotFoundException("Module tidak ditemukan")
            module = StudentModuleResponse.model_validate(raw_module)
            return module
        except Exception as e:
            raise e
