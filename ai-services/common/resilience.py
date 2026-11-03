import threading

from openai import AuthenticationError

from common import llm

SYSTEMIC_ERRORS = (*llm.RETRYABLE, AuthenticationError)


class Breaker:
    def __init__(self, threshold: int):
        self.threshold, self.streak, self.tripped, self.lock = threshold, 0, False, threading.Lock()

    def success(self) -> None:
        with self.lock:
            self.streak = 0

    def failure(self, error: Exception) -> None:
        if is_systemic(error):
            with self.lock:
                self.streak += 1
                self.tripped = self.tripped or self.streak >= self.threshold


def is_systemic(error: Exception) -> bool:
    return isinstance(error, SYSTEMIC_ERRORS) or (isinstance(error, RuntimeError) and "AZURE_OPENAI" in str(error))
