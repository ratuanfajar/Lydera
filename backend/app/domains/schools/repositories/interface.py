from abc import ABC, abstractmethod
from app.domains.schools.models.school import School
from app.domains.schools.schemas import SchoolCreate

class SchoolRepositoryInterface(ABC):
    @abstractmethod
    async def create_school(self, dto:SchoolCreate) -> School:
        raise NotImplementedError



