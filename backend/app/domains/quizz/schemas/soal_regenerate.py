from typing import List, Optional, Union

from pydantic import BaseModel, Field


class StimulusRegenerateInput(BaseModel):
    source_reading_order_start: int
    source_reading_order_end: int
    readable_text: Optional[str] = None

class SoalClusterItemInput(BaseModel):
    id: Union[int, str]  
    bloom_level: int = Field(..., ge=1, le=6)

class RegenerateClusterRequest(BaseModel):
    chapter_id: int
    feedback: str = Field(..., min_length=3, description="Feedback guru untuk regenerasi")
    stimulus: StimulusRegenerateInput
    items: List[SoalClusterItemInput] = Field(..., min_items=1)