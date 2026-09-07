from app.utils.payload import Payload
from app.utils.role import Role
from app.core.response import set_response_message
from app.domains.users.models.teacher import Teacher
from app.domains.users.repositories.repository import TeacherRepositoryInterface, StudentRepositoryInterface, UserRepositoryInterface
from app.domains.users.schemas import TeacherCreate, StudentCreate, Login, ProfileResponse
from app.core.db import AsyncSession
from app.core.exceptions import ValidationException, NotFoundException
from app.core.security import create_access_token, hash_password, verify_password

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
            raise ValidationException("Email or password is invalid")

        is_verify = verify_password(dto.password, user.password)
        
        if not is_verify:
            raise ValidationException("Email or password is invalid")
        if user.teacher:
            profile_id = user.teacher.id
            role = Role.TEACHER  
        elif user.student:
            profile_id = user.student.id
            role = Role.STUDENT
        else:
            raise ValidationException("User profile does not exist")
        
        payload = Payload(
            sub=user.id,
            profile_id=profile_id,
            role=role
        )
        return create_access_token(payload.model_dump())

    async def get_profile(self, user_id) -> ProfileResponse:
        profile = await self.user_repo.get_profile(user_id)

        if profile is None:
            raise NotFoundException("User not found")
        
        return ProfileResponse.model_validate(
            profile,
            from_attributes=True,
        ).model_dump()

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
        db: AsyncSession,
    ):
        self.user_repo = user_repo
        self.student_repo = student_repo
        self.db = db

    async def create_student(self, dto: StudentCreate):
        async with self.db.begin():
            user = await self.user_repo.create_user(dto)
            student = await self.student_repo.create_student(
                user_id=user.id,
            )
            set_response_message("Berhasil membuat akun guru")
        return student