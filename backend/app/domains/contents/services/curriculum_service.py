from typing import List, Sequence

from app.core.exceptions import NotFoundException
from app.domains.contents.models import Fase
from app.domains.contents.repositories.interfaces.curriculum_interface import (
    CurriculumRepositoryInterface,
)
from app.domains.contents.schemas.cp_response import CpResponse


class CurriculumService:
    def __init__(self, repo: CurriculumRepositoryInterface):
        self.repo = repo

    async def get_all_fases(self) -> Sequence[Fase]:
        return await self.repo.get_all_fases()

    async def get_cps_by_fase_id(self, fase_id: int) -> List[CpResponse]:
        cps = await self.repo.get_cps_by_fase_id(fase_id)
        if not cps:
            raise NotFoundException("cps tidak ditemukan")
        return [CpResponse.model_validate(c) for c in cps]
