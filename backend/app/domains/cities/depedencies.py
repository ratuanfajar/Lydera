from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from core.db import get_db
from domains.cities.repositories.repository import CityRepository
from domains.cities.services import CityService

def get_city_repository(db: AsyncSession = Depends(get_db)) -> CityRepository:
    return CityRepository(db)

def get_city_service(repo: CityRepository = Depends(get_city_repository), db: AsyncSession = Depends(get_db)) -> CityService:
    return CityService(repo,db)