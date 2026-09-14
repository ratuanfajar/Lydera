from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.classrooms.models.classroom import Classroom
from app.domains.users.models.student import student_classrooms

async def seed_classrooms(session: AsyncSession) -> Classroom:
    
    ct = Classroom(name="Matematika Asik", code="SKA9102", grade=11, classroom_type_id=1, school_id=1, teacher_id=1)

    session.add(ct)
    await session.flush()

    assoc_stmt = insert(student_classrooms).values(
        student_id=1,
        classroom_id=ct.id
    )
    await session.execute(assoc_stmt)
    return ct