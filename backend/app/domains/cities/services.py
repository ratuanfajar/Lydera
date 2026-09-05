from core.response import set_response_message
from domains.cities.repositories.repository import CityRepositoryInterface, City
from domains.cities.models.city import City
from domains.cities.schemas import CityCreate
from core.db import AsyncSession

class CityService:
    def __init__(self,
                repo: CityRepositoryInterface,
                db: AsyncSession
                ):
        self.repo = repo
        self.db = db
        

    async def create_city(self, city: CityCreate) -> City:
        async with self.db.begin():
            city = await self.repo.create_city(city.name)
        return city

    async def get_list_city(self) -> list[City]:
        cities = await self.repo.get_list_city()
        return cities