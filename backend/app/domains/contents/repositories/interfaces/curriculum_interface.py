from abc import ABC, abstractmethod
from typing import Sequence

from app.domains.contents.models import Cp, Fase


class CurriculumRepositoryInterface(ABC):
    @abstractmethod
    async def get_all_fases(self) -> Sequence[Fase]: raise NotImplementedError

    @abstractmethod
    async def get_cps_by_fase_id(self, fase_id: int) -> Sequence[Cp]: raise NotImplementedError
