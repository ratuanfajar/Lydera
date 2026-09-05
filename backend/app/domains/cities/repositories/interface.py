from abc import ABC, abstractmethod
from domains.cities.models.city import City 

class CityRepositoryInterface(ABC):
    @abstractmethod
    async def create_city(self, name: str) -> City:
        raise NotImplementedError

    @abstractmethod
    async def get_list_city(self) -> list[City]:
        raise NotImplementedError