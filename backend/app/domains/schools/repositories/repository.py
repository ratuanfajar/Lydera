from app.domains.users.models.teacher import Teacher
from app.domains.schools.repositories.interface import SchoolRepositoryInterface
from app.domains.schools.schemas import SchoolCreate
from app.domains.schools.models.school import School
from sqlalchemy import select
from app.core.db import AsyncSession


class SchoolRepository(SchoolRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_school(self, dto: SchoolCreate) -> School:
        school = School(name=dto.name, city_id=dto.city_id)
        self.db.add(school)
        await self.db.flush()
        return school

    async def get_list_school(self, city_id: int) -> list[School]:
        stmt = (
            select(School)
            .where(School.city_id == city_id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def get_school_by_id(self, school_id: int, teacher_id) -> School | None:
        stmt = (
            select(School)
            .join(School.teachers)
            .where(
                School.id == school_id,
                Teacher.id == teacher_id
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().one_or_none()

