
TTL_3_MINUTES = 180

class QuizRedisKeys:
    @staticmethod
    def idempotency(key: str) -> str:
        return f"quiz:idem:{key}"

    @staticmethod
    def progress(quiz_request_id: int) -> str:
        return f"quiz:{quiz_request_id}:progress"

    @staticmethod
    def content(key: str) -> str:
        return f"quiz:content:{key}"

    @staticmethod
    def result(quiz_request_id: int) -> str:
        return f"quiz:result:{quiz_request_id}"

    @staticmethod
    def coverage(quiz_request_id: int) -> str:
        return f"quiz:coverage:{quiz_request_id}"

    @staticmethod
    def stream(quiz_request_id: int) -> str:
        return f"quiz:stream:{quiz_request_id}"
    
    @staticmethod
    def lock(key: str) -> str:
        return f"quiz:lock:{key}"
