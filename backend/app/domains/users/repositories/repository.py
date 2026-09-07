from pydantic import EmailStr
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload
from domains.users.repositories.interface import UserRepositoryInterface, TeacherRepositoryInterface, StudentRepositoryInterface
from domains.users.schemas import UserCredentials
from domains.users.models.user import User
from domains.users.models.teacher import Teacher
from domains.users.models.student import Student
from core.db import AsyncSession


class UserRepository(UserRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, dto: UserCredentials) -> User:
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