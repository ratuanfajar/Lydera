from abc import ABC, abstractmethod

from app.domains.classrooms.models.classroom_type import ClassroomType
from app.domains.classrooms.models.classroom import Classroom
from app.utils.role import AllowedRole, Role
from app.domains.classrooms.schemas import ClassroomCreate, ClassroomInfoResponse

class ClassroomRepositoryInterface(ABC):
    @abstractmethod
    async def create_classroom(self, dto: ClassroomCreate, teacher_id: int) -> Classroom:
        raise NotImplementedError

    @abstractmethod
    async def get_classrooms(self, profile_id: int, role: Role) -> list[Classroom]:
        raise NotImplementedError

    @abstractmethod
    async def get_classroom_by_id(self, classroom_id: int, profile_id: int, role: Role) -> Classroom | None:
        raise NotImplementedError

    @abstractmethod
    async def join_classroom(self, code: str, student_id: int) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def get_classroom_info(self, classroom_id: str, student_id: int, role:Role) -> ClassroomInfoResponse | None:
        raise NotImplementedError

    @abstractmethod
    async def has_access(self, classroom_id: str, profile_id: int, role:AllowedRole) -> bool:
        raise NotImplementedError

class ClassroomTypeRepositorInterface(ABC):
    @abstractmethod
    async def get_classroom_types(self) -> list[ClassroomType]:
        raise NotImplementedError
    