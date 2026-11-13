TTL_3_MINUTES = 180
TTL_30_MINUTES = 1800

class ChapterRedisKeys:
    @staticmethod
    def chapter_meta(chapter_id: int) -> str:
        return f"chapter:{chapter_id}:meta"

    @staticmethod
    def chapter_block(chapter_id: int, block_id: int) -> str:
        return f"chapter:{chapter_id}:block_id:{block_id}"

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
