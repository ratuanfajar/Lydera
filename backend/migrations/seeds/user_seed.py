from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import hash_password
from app.domains.users.models.user import User  

async def seed_users(session: AsyncSession) -> tuple[User, User]:
    hashed_pwd = hash_password("12345678")
    
    teacher_user = User(email="teacher@gmail.com", password=hashed_pwd)
    student_user = User(email="student@gmail.com", password=hashed_pwd)
    
    session.add_all([teacher_user, student_user])
    await session.flush()
    
    return teacher_user, student_user