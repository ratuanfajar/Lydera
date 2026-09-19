from pydantic import BaseModel, ConfigDict


class CpResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    fase_id: int
    domain: str
    cp_text: str
