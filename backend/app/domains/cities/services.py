from core.response import set_response_message
from domains.cities.repositories.repository import CityRepositoryInterface, City
from domains.cities.models.city import City
from domains.cities.schemas import CityCreate

class CityService:
    def __init__(self, repo: CityRepositoryInterface):
        self.repo = repo

    async def create_city(self, city: CityCreate) -> City:
        city = await self.repo.create_city(city.name)
        set_response_message("City created successfully")
        return city

    async def get_list_city(self) -> list[City]:
        cities = await self.repo.get_list_city()
        return cities