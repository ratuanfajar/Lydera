# from fastapi import Depends
# from sqlalchemy.ext.asyncio import AsyncSession
# from core.database import get_db
# from domains.user.repository import UserRepository
# from domains.user.service import UserService

# def get_user_repository(db: AsyncSession = Depends(get_db)) -> UserRepository:
#     return UserRepository(db)

# def get_user_service(repo: UserRepository = Depends(get_user_repository)) -> UserService:
#     return UserService(repo)