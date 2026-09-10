from pydantic import EmailStr
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload, selectinload
from app.core.security import hash_password
from app.domains.users.repositories.interface import UserRepositoryInterface, TeacherRepositoryInterface, StudentRepositoryInterface
from app.domains.users.schemas import UserCredentials
from app.domains.users.models.user import User
from app.domains.users.models.teacher import Teacher
from app.domains.users.models.student import Student
from app.core.db import AsyncSession
from app.domains.users.schemas.student_tasks_response import StudentTaskResponse
from app.domains.contents.models import Module, ModuleProgress, ModuleStatus


class UserRepository(UserRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, dto: UserCredentials) -> User:
        hashed_password = hash_password(dto.password)
        dto.password = hashed_password
        user = User(email=dto.email, password=dto.password)
        self.db.add(user)
        await self.db.flush()
        return user

    async def get_profile(self, user_id: int) -> User | None:
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(
                joinedload(User.teacher),
                joinedload(User.student),
            )
        )

        result = await self.db.execute(stmt)

        return result.scalar_one_or_none()

    async def get_by_email(self, email: EmailStr) -> User | None:
        stmt = (
            select(User)
            .where(User.email == email)
            .options(
                joinedload(User.teacher),
                joinedload(User.student),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    

class TeacherRepository(TeacherRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_teacher(self, user_id:int) -> Teacher:
        teacher = Teacher(
            user_id=user_id,
        )
        self.db.add(teacher)
        await self.db.flush()
        return teacher

class StudentRepository(StudentRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_student(self, user_id:int ) -> Student:
        student = Student(
            user_id=user_id,
        )
        self.db.add(student)
        await self.db.flush()
        return student

    async def get_task_counts(self, classroom_id: int, student_id: int) -> dict[str, int]:
        stmt = (
            select(func.count(Module.id))
            .outerjoin(
                ModuleProgress,
                (ModuleProgress.module_id == Module.id) & (ModuleProgress.student_id == student_id)
            )
            .where(
                Module.classroom_id == classroom_id,
                Module.status == ModuleStatus.PUBLISH,
                or_(
                    ModuleProgress.id.is_(None),
                    ModuleProgress.is_done == False,
                ),
            )
        )

        modules_not_done = await self.db.scalar(stmt) or 0

        return {
            "modules_not_done":modules_not_done,
            "exam_not_done":0, 
        }