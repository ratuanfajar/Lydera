from pydantic import BaseModel, ConfigDict

class ModuleProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id:int
    module_id:int
    progress_percentage:int
    is_done: bool