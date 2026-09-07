from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from domains.cities.repositories.interface import CityRepositoryInterface
from domains.cities.models.city import City


class CityRepository(CityRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_city(self, name: str) -> City:
        city = City(name=name)
        self.db.add(city)
        await self.db.flush()
        return city

    async def get_list_city(self) -> list[City]:
        result = await self.db.execute(select(City))
        return list(result.scalars().all())