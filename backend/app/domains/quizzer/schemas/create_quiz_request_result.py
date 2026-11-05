from dataclasses import dataclass

@dataclass
class CreateQuizRequestResult:
    quiz_request_id: int
    status: str
    is_cached: bool
    should_enqueue: bool
    idem_digest: str
    content_fingerprint: str



