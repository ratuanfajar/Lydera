from domains.schools.repositories.interface import SchoolRepositoryInterface
from domains.schools.schemas import SchoolCreate
from domains.schools.models.school import School
from core.db import AsyncSession


class SchoolRepository(SchoolRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_school(self, dto: SchoolCreate) -> School:
        school = School(name=dto.name, city_id=dto.city_id)
        self.db.add(school)
        await self.db.flush()
        return school
