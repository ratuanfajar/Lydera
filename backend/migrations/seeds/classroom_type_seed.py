from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.classrooms.models.classroom_type import ClassroomType

async def seed_classroom_types(session: AsyncSession) -> ClassroomType:
    ct = ClassroomType(name="Matematika")
    session.add(ct)
    await session.flush()
    return ct