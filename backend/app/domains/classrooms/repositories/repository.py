
from app.domains.classrooms.models.classroom_type import ClassroomType
from app.domains.classrooms.models.classroom import Classroom
from app.utils.role import Role
from app.domains.classrooms.schemas import ClassroomCreate, ClassroomStudentResponse
from app.domains.classrooms.repositories.interface import ClassroomRepositoryInterface, ClassroomTypeRepositorInterface
from app.core.db import AsyncSession
from app.domains.users.models.student import student_classrooms
import string
from nanoid import generate
from sqlalchemy.exc import IntegrityError
from sqlalchemy import insert, select
from sqlalchemy.orm import joinedload
from app.domains.schools.models.school import School

class ClassroomRepository(ClassroomRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_classroom(self, dto: ClassroomCreate, teacher_id: int) -> Classroom:
        alphabet = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        while True:
            random_code = generate(alphabet, 7)
            
            new_classroom = Classroom(
                **dto.model_dump(),     
                teacher_id=teacher_id,
                code=random_code
            )
            
            self.db.add(new_classroom)
            
            try:
                async with self.db.begin_nested():
                    await self.db.flush()
                break
            except IntegrityError:
                self.db.expunge(new_classroom)
                continue
        await self.db.refresh(new_classroom,["classroom_type"])
        return new_classroom

    async def get_classrooms(self, profile_id: int, role: Role) -> list[Classroom]:
        stmt = select(Classroom).options(joinedload(Classroom.classroom_type))
        
        if role == Role.TEACHER:
            stmt = stmt.where(Classroom.teacher_id == profile_id)
        elif role == Role.STUDENT:
            stmt = stmt.where(Classroom.students.any(id=profile_id))
            
        result = await self.db.execute(stmt)
        classrooms = result.scalars().all()
        return classrooms

    async def get_classroom_by_id(self, classroom_id: int, profile_id: int, role: Role) -> Classroom | None:
        stmt = (
            select(Classroom)
            .options(joinedload(Classroom.classroom_type))
            .where(Classroom.id == classroom_id)
        )
        
        if role == Role.TEACHER:
            stmt = stmt.where(Classroom.teacher_id == profile_id)
        elif role == Role.STUDENT:
            stmt = stmt.where(Classroom.students.any(id=profile_id))
            
        result = await self.db.execute(stmt)
        classroom = result.scalar_one_or_none()
        
        return classroom

    async def join_classroom(self, code: str, student_id: int) -> bool:
        stmt = select(Classroom).where(Classroom.code == code)
        result = await self.db.execute(stmt)
        classroom = result.scalar_one_or_none()
        if not classroom:
            return False
            
        stmt_insert = insert(student_classrooms).values(student_id=student_id, classroom_id=classroom.id)
        await self.db.execute(stmt_insert)
        
        return True

    async def get_classroom_student(self, classroom_id: int, student_id: int) -> ClassroomStudentResponse | None:
        stmt = (
            select(
                School.name.label("school_name"),
                Classroom.grade.label("grade_class"),
                ClassroomType.name.label("classroom_type"),
            )
            .select_from(Classroom)
            .join(School, Classroom.school_id == School.id)
            .join(ClassroomType, Classroom.classroom_type_id == ClassroomType.id)
            .join(
                student_classrooms, 
                student_classrooms.c.classroom_id == Classroom.id
            )
            .where(
                Classroom.id == classroom_id,
                student_classrooms.c.student_id == student_id,
            )
        )

        result = await self.db.execute(stmt)
        row = result.mappings().one_or_none()

        if not row:
            return None

        return ClassroomStudentResponse.model_validate(row)

class ClassroomTypeRepository(ClassroomTypeRepositorInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_classroom_types(self) -> list[ClassroomType]:
        stmt = select(ClassroomType)
        result = await self.db.execute(stmt)
        types = result.scalars().all()
        return types
    