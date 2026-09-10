from app.utils.role import Role
from app.core.exceptions import ForbiddenException, NotFoundException
from app.core.response import set_response_message
from app.domains.classrooms.repositories.repository import ClassroomRepositoryInterface, ClassroomTypeRepositorInterface
from app.domains.classrooms.models.classroom import Classroom
from app.domains.classrooms.models.classroom_type import ClassroomType
from app.domains.classrooms.schemas import ClassroomCreate, ClassroomTypeResponse, ClassroomResponse, ClassroomStudentResponse
from app.core.db import AsyncSession

class ClassroomService:
    def __init__(self,
                 repo: ClassroomRepositoryInterface,
                 db: AsyncSession
                 ):
        self.repo = repo
        self.db = db

    async def create_classroom(self, dto: ClassroomCreate, teacher_id: int) -> ClassroomResponse:
        try:
            classroom = await self.repo.create_classroom(dto, teacher_id)
            await self.db.commit()
            return ClassroomResponse.model_validate(classroom)
        except Exception as e:
            await self.db.rollback()
            raise e

    async def get_classrooms(self, profile_id: int, role: Role) -> list[ClassroomResponse]:
        classrooms = await self.repo.get_classrooms(profile_id, role)
        return [ClassroomResponse.model_validate(c) for c in classrooms]

    async def get_classroom_by_id(self, classroom_id: int, profile_id: int, role: Role) -> ClassroomResponse:
        classroom = await self.repo.get_classroom_by_id(classroom_id, profile_id, role)
        
        if not classroom:
            raise NotFoundException("Classroom not found or you don't have access")
            
        return ClassroomResponse.model_validate(classroom)

    async def join_classroom(self, code: str, student_id: int) -> bool:
        try:
            success = await self.repo.join_classroom(code, student_id)
            
            if not success:
                raise NotFoundException("Classroom code is invalid or not found")
                
            await self.db.commit()
            return success
        except Exception as e:
            await self.db.rollback()
            raise e


class ClassroomTypeService:
    def __init__(self,
                 repo: ClassroomTypeRepositorInterface,
                 db: AsyncSession
                 ):
        self.repo = repo
        self.db = db

    async def get_classroom_types(self) -> list[ClassroomTypeResponse]:
        types = await self.repo.get_classroom_types()
        return [ClassroomTypeResponse.model_validate(t) for t in types]
    