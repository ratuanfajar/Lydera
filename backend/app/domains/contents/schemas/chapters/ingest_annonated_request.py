from pydantic import BaseModel


class IngestAnnotatedRequest(BaseModel):
    annotation_path: str