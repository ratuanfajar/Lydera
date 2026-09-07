from app.core.exceptions import ForbiddenException
from app.core.response import set_response_message
from app.domains.schools.repositories.repository import SchoolRepositoryInterface
from app.domains.schools.models.school import School
from app.domains.schools.schemas import SchoolCreate
from app.core.db import AsyncSession

class SchoolService:
    def __init__(self,
                repo: SchoolRepositoryInterface,
                db: AsyncSession
                ):
        self.repo = repo
        self.db = db
        

    async def create_school(self, dto: SchoolCreate) -> School:
        async with self.db.begin():
            school = await self.repo.create_school(dto)
        return school

    async def get_list_school(self, city_id: int) -> list[School]:
        schools = await self.repo.get_list_school(city_id)
        return schools

    async def get_school(self, school_id: int, teacher_id: int) -> School:
        school = await self.repo.get_school_by_id(school_id,teacher_id)
        if school is None:
            raise ForbiddenException('Forbidden school access')
        return school