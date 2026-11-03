from app.utils.payload import Payload
from app.utils.role import AllowedRole, Role
from app.core.response import set_response_message
from app.domains.users.models.teacher import Teacher
from app.domains.classrooms.repositories.repository import ClassroomRepositoryInterface
from app.domains.users.repositories.repository import TeacherRepositoryInterface, StudentRepositoryInterface, UserRepositoryInterface
from app.domains.users.schemas import TeacherCreate, StudentCreate, Login, ProfileResponse, StudentDashboardRequest, StudentDashboardResponse
from app.core.db import AsyncSession
from app.core.exceptions import ValidationException, NotFoundException
from app.core.security import create_access_token, verify_password
from app.domains.users.schemas.teacher_dashboard_request import TeacherDashboardRequest
from app.domains.users.schemas.teacher_dashboard_response import TeacherDashboardResponse

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
        classroom_repo: ClassroomRepositoryInterface,
        teacher_repo: TeacherRepositoryInterface,
        db: AsyncSession,
    ):
        self.user_repo = user_repo
        self.teacher_repo = teacher_repo
        self.classroom_repo = classroom_repo
        self.db = db

    async def create_teacher(self, dto: TeacherCreate) -> Teacher:
        async with self.db.begin():
            user = await self.user_repo.create_user(dto)
            teacher = await self.teacher_repo.create_teacher(
                user_id=user.id,
            )
            set_response_message("Berhasil membuat akun guru")
        return teacher
    
    async def dashboard_teacher(self, dto: TeacherDashboardRequest, teacher_id:int, user_id:int) -> TeacherDashboardResponse:
        try:
            classroom_info = await self.classroom_repo.get_classroom_info(dto.classroom_id, teacher_id, Role.TEACHER)
            dashboard_raw = await self.teacher_repo.get_dashboard(dto.classroom_id, dto.limit)
            profile = await self.user_repo.get_profile(user_id)

            if not profile or not profile.teacher:
                raise NotFoundException("User tidak ditemukan")
            
            if not classroom_info:
                raise NotFoundException("User tidak punya kelas ini")
            
            await self.db.commit()
            return TeacherDashboardResponse(
                classroom_info=classroom_info,
                teacher_email=profile.email,
                **dashboard_raw
            )
        
        except Exception as e:
            raise e

class StudentService:
    def __init__(
        self,
        user_repo: UserRepositoryInterface,
        student_repo: StudentRepositoryInterface,
        classroom_repo: ClassroomRepositoryInterface,
        db: AsyncSession
    ):
        self.user_repo = user_repo
        self.student_repo = student_repo
        self.classroom_repo = classroom_repo
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
        try:
            classroom_info = await self.classroom_repo.get_classroom_info(dto.classroom_id, student_id, Role.STUDENT)
            tasks = await self.student_repo.get_task_counts(dto.classroom_id, student_id)
            profile = await self.user_repo.get_profile(user_id)

            if not profile or not profile.student:
                raise NotFoundException("User tidak ditemukan")
            
            if not classroom_info:
                raise NotFoundException("User tidak punya kelas ini")

            return StudentDashboardResponse(
                classroom_info=classroom_info,
                exam_not_done=tasks.get("exam_not_done"),
                modules_not_done=tasks.get("modules_not_done"),
                student_email=profile.email
            )
        
        except Exception as e:
            raise e
