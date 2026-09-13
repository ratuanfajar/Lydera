from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.users.models.student import Student

async def seed_students(session: AsyncSession, user_id: int) -> Student:
    student = Student(
        user_id=user_id,
        nis="12345",
        nisn="0012345678",
        grade=10
    )
    session.add(student)
    await session.flush()
    return student