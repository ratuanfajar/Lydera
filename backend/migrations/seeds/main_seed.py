import asyncio

from app.core.db import AsyncSessionLocal
# Use relative imports within the package
import app.core.model_registry

from .city_seed import seed_cities
from .classroom_type_seed import seed_classroom_types
from .school_seed import seed_schools
from .fase_cp_seed import seed_fase_and_cp
from .user_seed import seed_users
from .teacher_seed import seed_teachers
from .student_seed import seed_students

async def run_all_seeds():
    async with AsyncSessionLocal() as session:
        async with session.begin():  # Auto-commits on block exit, rolls back on error
            print("🌱 Starting predictable database seed...")
            
            # 1. Base Lookup Data
            city = await seed_cities(session)
            await seed_classroom_types(session)
            school = await seed_schools(session, city_id=city.id)
            await seed_fase_and_cp(session)
            
            # 2. Users (Hashed password "12345678")
            teacher_user, student_user = await seed_users(session)
            
            # 3. Domain Entities
            await seed_teachers(session, user_id=teacher_user.id, school_id=school.id)
            await seed_students(session, user_id=student_user.id)
            
            print("✅ All seed data inserted successfully!")

if __name__ == "__main__":
    asyncio.run(run_all_seeds())