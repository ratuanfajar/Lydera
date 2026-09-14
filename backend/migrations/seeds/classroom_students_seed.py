from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.users.models.student import student_classrooms

async def seed_student_classroom(
    session: AsyncSession, 
    student_id: int, 
    classroom_id: int
) -> None:
    """Inserts a single student enrollment record into the junction table."""
    stmt = insert(student_classrooms).values(
        student_id=student_id,
        classroom_id=classroom_id,
    )
    await session.execute(stmt)
    await session.flush()