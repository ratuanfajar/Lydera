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
from app.domains.classrooms.models.classroom import Classroom
from app.domains.users.models.student import student_classrooms


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
    
    async def get_dashboard(self, classroom_id:int, limit:int) -> dict:
        modules_count = (
            select(func.count(Module.id))
            .where(Module.classroom_id == classroom_id, Module.status == ModuleStatus.PUBLISH, Module.deleted_at.is_(None))
            .scalar_subquery()
        )

        # exams_count = 0

        students_count = (
            select(func.count(student_classrooms.c.student_id))
            .where(student_classrooms.c.classroom_id == classroom_id)
            .scalar_subquery()
        )

        summary_stmt = select(
            modules_count.label("total_modules"),
            # exams_count.label("total_exams"),
            students_count.label("total_students"),
        ).where(Classroom.id == classroom_id)

        summary_res = (await self.db.execute(summary_stmt)).one_or_none()
        if not summary_res:
            return None

        modules_stmt = (
            select(Module)
            .where(
                Module.classroom_id == classroom_id,
                Module.status == ModuleStatus.PUBLISH,
                Module.deleted_at.is_(None)
            )
            .order_by(Module.created_at.desc())
            .limit(limit)
        )
        newest_modules = (await self.db.scalars(modules_stmt)).all()

        newest_exams = []

        return {
            "total_modules": summary_res.total_modules,
            "total_exams": 0,
            "total_students": summary_res.total_students,
            "newest_modules": newest_modules,
            "newest_exams": newest_exams,
        }

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