from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.users.models.teacher import Teacher


async def seed_teachers(session: AsyncSession, user_id: int, school_id: int) -> Teacher:
    teacher = Teacher(user_id=user_id, school_id=school_id)
    session.add(teacher)
    await session.flush()
    return teacher