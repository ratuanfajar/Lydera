from pydantic import BaseModel, ConfigDict
class ClassroomInfoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    school_name: str
    code: str | None = None
    grade_class: int
    classroom_type: str