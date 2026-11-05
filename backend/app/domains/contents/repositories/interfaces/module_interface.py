from abc import ABC, abstractmethod
from typing import Sequence

from app.domains.contents.models import Module, ModuleStatus
from app.domains.contents.schemas.module.student_module_request import StudentModuleStatus
from app.domains.contents.schemas.module.teacher_module_request import TeacherModuleStatus


class ModuleRepositoryInterface(ABC):
    @abstractmethod
    async def get_module_by_id(self, module_id: int) -> Module | None: raise NotImplementedError

    @abstractmethod
    async def create_module_teacher(self, title: str, description: str, status: ModuleStatus, classroom_id: int, teacher_id: int, fase_id: int | None) -> Module | None: raise NotImplementedError

    @abstractmethod
    async def get_all_modules_student(self, classroom_id: int, student_id: int, status: StudentModuleStatus) -> Sequence[Module]: raise NotImplementedError

    @abstractmethod
    async def get_detail_module_student(self, module_id: int, classroom_id: int, student_id: int) -> Module | None: raise NotImplementedError

    @abstractmethod
    async def get_all_modules_teachers(self, classroom_id: int, teacher_id: int, status: TeacherModuleStatus, search: str | None) -> Sequence[Module]: raise NotImplementedError

    @abstractmethod
    async def get_detail_module_teacher(self, module_id: int, classroom_id: int, teacher_id: int) -> Module | None: raise NotImplementedError

    @abstractmethod
    async def delete_module_teacher(self, module_id: int, classroom_id: int, teacher_id: int) -> bool: raise NotImplementedError

    @abstractmethod
    async def publish_module(self, module_id: int, teacher_id: int) -> bool: raise NotImplementedError
