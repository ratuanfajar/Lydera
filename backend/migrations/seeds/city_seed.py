from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.cities.models.city import City

async def seed_cities(session: AsyncSession) -> City:
    city = City(name="Cimahi")
    session.add(city)
    await session.flush()
    return city