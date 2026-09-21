from pydantic import BaseModel

class AddStepRequest(BaseModel):
    step : str