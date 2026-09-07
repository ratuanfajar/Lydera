from core.response import set_response_message
from domains.schools.repositories.repository import SchoolRepositoryInterface
from domains.schools.models.school import School
from domains.schools.schemas import SchoolCreate
from core.db import AsyncSession

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