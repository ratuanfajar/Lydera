from app.utils.payload import Payload
from app.utils.role import AllowedRole, Role
from app.core.response import set_response_message
from app.domains.users.models.teacher import Teacher
from app.domains.classrooms.repositories.repository import ClassroomRepositoryInterface
from app.domains.users.repositories.repository import TeacherRepositoryInterface, StudentRepositoryInterface, UserRepositoryInterface
from app.domains.users.schemas import TeacherCreate, StudentCreate, Login, ProfileResponse, StudentDashboardRequest, StudentDashboardResponse
from app.domains.users.schemas.student_tasks_response import StudentTaskResponse
from app.core.db import AsyncSession
from app.core.exceptions import ForbiddenException, ValidationException, NotFoundException
from app.core.security import create_access_token, verify_password
from app.domains.users.schemas.student_dashboard_request import StudentTaskStatus
from app.domains.users.schemas.student_tasks_request import StudentTaskRequest
from app.domains.contents.repositories.interface import ContentRepositoryInterface
from app.domains.contents.schemas.module.student_module_response import StudentModuleResponse
from app.domains.contents.schemas.module.student_module_request import StudentModuleRequest, StudentModuleStatus
from app.domains.contents.schemas.module.student_module_detail_request import StudentModuleDetailRequest
from app.domains.contents.schemas.blocks.block_response import BlockResponse
from app.domains.contents.schemas.chapters.student_chapter_detail_response import StudentChapterDetailResponse
from app.domains.contents.models.chapter import Chapter

class UserService:
    def __init__(
        self,
        user_repo: UserRepositoryInterface,
        db: AsyncSession,
    ):
        self.user_repo = user_repo
        self.db = db

    async def login(self, dto: Login) -> str :
        user = await self.user_repo.get_by_email(dto.email)

        if user is None:
            raise ValidationException("Email atau  password invalid")

        is_verify = verify_password(dto.password, user.password)
        
        if not is_verify:
            raise ValidationException("Email atau password is invalid")
        
        if (dto.role == AllowedRole.TEACHER and not user.teacher) or (dto.role == AllowedRole.STUDENT and not user.student):
            raise ValidationException("Role invalid")
    
        if user.teacher:
            profile_id = user.teacher.id
            role = Role.TEACHER  
        elif user.student:
            profile_id = user.student.id
            role = Role.STUDENT
        else:
            raise ValidationException("User profile tidak ada")
        
        payload = Payload(
            sub=str(user.id),
            profile_id=profile_id,
            role=role
        )
        return create_access_token(payload.model_dump(mode="json"))

    async def get_profile(self, user_id) -> ProfileResponse:
        profile = await self.user_repo.get_profile(user_id)

        if profile is None:
            raise NotFoundException("User tidak ditemukan")
        
        return ProfileResponse.model_validate(
            profile,
            from_attributes=True,
        )

class TeacherService:
    def __init__(
        self,
        user_repo: UserRepositoryInterface,
        teacher_repo: TeacherRepositoryInterface,
        db: AsyncSession,
    ):
        self.user_repo = user_repo
        self.teacher_repo = teacher_repo
        self.db = db

    async def create_teacher(self, dto: TeacherCreate) -> Teacher:
        async with self.db.begin():
            user = await self.user_repo.create_user(dto)
            teacher = await self.teacher_repo.create_teacher(
                user_id=user.id,
            )
            set_response_message("Berhasil membuat akun guru")
        return teacher

class StudentService:
    def __init__(
        self,
        user_repo: UserRepositoryInterface,
        student_repo: StudentRepositoryInterface,
        classroom_repo: ClassroomRepositoryInterface,
        content_repo: ContentRepositoryInterface,
        db: AsyncSession
    ):
        self.user_repo = user_repo
        self.student_repo = student_repo
        self.classroom_repo = classroom_repo
        self.content_repo = content_repo
        self.db = db

    async def create_student(self, dto: StudentCreate):
        async with self.db.begin():
            user = await self.user_repo.create_user(dto)
            student = await self.student_repo.create_student(
                user_id=user.id,
            )
            set_response_message("Berhasil membuat akun murid")
        return student

    async def dashboard_student(self, dto: StudentDashboardRequest, student_id: int, user_id:int) -> StudentDashboardResponse:
        # Kasih Redis
        try:
            classroom_info = await self.classroom_repo.get_classroom_student(dto.classroom_id, student_id)
            tasks = await self.student_repo.get_task_counts(dto.classroom_id, student_id)
            profile = await self.user_repo.get_profile(user_id)

            if not profile or not profile.student:
                raise NotFoundException("User tidak ditemukan")
            
            if not classroom_info:
                raise NotFoundException("User tidak punya kelas ini")

            await self.db.commit()
            return StudentDashboardResponse(
                classroom_info=classroom_info,
                tasks=tasks,
                student_email=profile.email
            )
        
        except Exception as e:
            raise e
        
    async def get_tasks_student(self, dto: StudentTaskRequest, student_id: int) -> StudentTaskResponse:
            try:
                match dto.status:
                    case StudentTaskStatus.ALL:
                        modules = await self.content_repo.get_all_modules_student(dto.classroom_id, student_id, StudentModuleStatus.NOT_DONE)
                        exams = []
        
                    case StudentTaskStatus.MODULE:
                        modules = await self.content_repo.get_all_modules_student(dto.classroom_id, student_id, StudentModuleStatus.NOT_DONE)
                        exams = []
        
                    case StudentTaskStatus.EXAM:
                        modules = []
                        # exams = await self.get_exams(dto.classroom_id, student_id)
                        exams = []
        
                    case _:
                        raise ValueError(f"Status tidak valid: {dto.status}")
    
                await self.db.commit()
                return StudentTaskResponse(
                    exams=exams,
                    modules=modules
                )
            
            except Exception as e:
                raise e
            
    async def get_student_modules(self, dto: StudentModuleRequest, student_id: int) -> list[StudentModuleResponse]:
            try:
                raw_modules = await self.content_repo.get_all_modules_student(dto.classroom_id, student_id, dto.status)
                modules = [StudentModuleResponse.model_validate(m) for m in raw_modules]
                return modules
            except Exception as e:
                raise e
            
    async def get_student_module(self, dto: StudentModuleDetailRequest, student_id: int, module_id:int) -> StudentModuleResponse:
            try:
                raw_module = await self.content_repo.get_detail_module_student(module_id,dto.classroom_id, student_id)
                if not raw_module:
                    raise NotFoundException("Module tidak ditemukan")
                module = StudentModuleResponse.model_validate(raw_module)
                return module
            except Exception as e:
                raise e
            
    async def start_chapter(self, student_id: int, chapter_id: int) -> StudentChapterDetailResponse:
        has_access = await self.content_repo.validate_student_chapter_access(chapter_id, student_id)
        if not has_access:
            raise ForbiddenException(detail="Anda tidak memiliki akses ke chapter ini.")
        await self.content_repo.student_upsert_chapter_progress(student_id=student_id, chapter_id=chapter_id)

        chapter = await self.content_repo.student_get_blocks_by_chapter_id(chapter_id=chapter_id, student_id=student_id)
        if not chapter:
            raise NotFoundException(detail="Chapter tidak ditemukan.")
        
        return StudentChapterDetailResponse.model_validate(chapter)

    async def mark_chapter_as_completed(self, student_id: int, chapter_id: int) -> bool:
        has_access = await self.content_repo.validate_student_chapter_access(chapter_id, student_id)
        if not has_access:
            raise ForbiddenException("Anda tidak memiliki akses ke chapter ini.")
        
        updated = await self.content_repo.student_update_chapter_progress(
            student_id=student_id, 
            chapter_id=chapter_id
        ) 
        if not updated:
            raise NotFoundException(
                detail="Progres chapter tidak ditemukan."
            )
        
        return True
            