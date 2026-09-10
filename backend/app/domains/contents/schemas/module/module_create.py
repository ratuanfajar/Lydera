from app.domains.contents.models import ModuleStatus
from pydantic import BaseModel


class ModuleCreate(BaseModel):
    title: str
    description: str
    fase_id: int
    classroom_id: int
    status: ModuleStatus | None = ModuleStatus.DRAFT



