from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.schools.models.school import School

async def seed_schools(session: AsyncSession, city_id: int) -> School:
    school = School(name="SLBN A. Citeureup", city_id=city_id)
    session.add(school)
    await session.flush()
    return school