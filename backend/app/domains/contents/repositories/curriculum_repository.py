from typing import Sequence

from sqlalchemy import select

from app.core.db import AsyncSession
from app.domains.contents.models import Cp, Fase
from app.domains.contents.repositories.interfaces.curriculum_interface import (
    CurriculumRepositoryInterface,
)


class CurriculumRepository(CurriculumRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_fases(self) -> Sequence[Fase]:
        stmt = select(Fase).order_by(Fase.kode)
        result = await self.db.scalars(stmt)
        return result.all()

    async def get_cps_by_fase_id(self, fase_id: int) -> Sequence[Cp]:
        stmt = select(Cp).where(Cp.fase_id == fase_id)
        result = await self.db.scalars(stmt)
        return result.all()
