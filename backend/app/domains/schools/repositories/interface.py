from abc import ABC, abstractmethod
from domains.schools.models.school import School
from domains.schools.schemas import SchoolCreate

class SchoolRepositoryInterface(ABC):
    @abstractmethod
    async def create_school(self, dto:SchoolCreate) -> School:
        raise NotImplementedError



