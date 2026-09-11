from abc import ABC, abstractmethod

from pydantic import EmailStr
from app.domains.users.schemas import StudentCreate, TeacherCreate, UserCredentials
from app.domains.users.schemas.student_tasks_response import StudentTaskResponse
from app.domains.users.models.teacher import Teacher
from app.domains.users.models.user import User
from app.domains.users.models.student import Student

class UserRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_email(self, email: EmailStr) -> User | None:
        raise NotImplementedError
    
    @abstractmethod
    async def get_profile(self, user_id: int) -> User | None:
        raise NotImplementedError

    @abstractmethod
    async def create_user(self, dto: UserCredentials) -> User:
        raise NotImplementedError

class TeacherRepositoryInterface(ABC):
    @abstractmethod
    async def create_teacher(self, dto:TeacherCreate) -> Teacher:
        raise NotImplementedError
    @abstractmethod
    async def get_dashboard(self, classroom_id:int, limit:int) -> dict:
        raise NotImplementedError

class StudentRepositoryInterface(ABC):
    @abstractmethod
    async def create_student(self, dto:StudentCreate) -> Student:
        raise NotImplementedError

    @abstractmethod
    async def get_task_counts(self, classroom_id:int , student_id: int) -> dict[str, int]:
        raise NotImplementedError