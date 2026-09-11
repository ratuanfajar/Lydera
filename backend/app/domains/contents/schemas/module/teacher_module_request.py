from typing import Annotated, Optional
from enum import Enum
from fastapi import Query
from pydantic import BaseModel

from app.domains.contents.models.module import ModuleStatus

class TeacherModuleStatus(str, Enum):
    ALL = "Semua"
    DRAFT = ModuleStatus.DRAFT.value
    PUBLISH = ModuleStatus.PUBLISH.value

class TeacherModuleRequest(BaseModel):
    classroom_id: Annotated[
        int,
        Query(
            gt=0, 
            description="ID Class Student",
            examples=[1]
        )
    ]

    search: Annotated[
        Optional[str],
        Query(
            description="Pencarian berdasarkan nama modul/bab",
            examples=["Matematika"]
        )
    ] = None

    status: Annotated[
        TeacherModuleStatus,
        Query(
            examples=[TeacherModuleStatus.ALL],
            description="Filter tasks by status: 'Semua', 'Draft', or 'Publish'"
        )
    ] = TeacherModuleStatus.ALL