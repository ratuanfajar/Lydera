from pydantic import BaseModel, ConfigDict
class ClassroomStudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    school_name: str
    grade_class: int
    classroom_type: str