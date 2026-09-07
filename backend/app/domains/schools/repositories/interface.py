from abc import ABC, abstractmethod
from app.domains.schools.models.school import School
from app.domains.schools.schemas import SchoolCreate

class SchoolRepositoryInterface(ABC):
    @abstractmethod
    async def create_school(self, dto:SchoolCreate) -> School:
        raise NotImplementedError

    @abstractmethod
    async def get_list_school(self, city_id: int) -> list[School]:
        raise NotImplementedError

    @abstractmethod
    async def get_school_by_id(self, school_id: int, teacher_id) -> School:
        raise NotImplementedError



