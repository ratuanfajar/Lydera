import os

import pytest

for name in ("SEARCH_API_KEY", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "EMBEDDING_API_KEY"):
    os.environ[name] = ""


@pytest.fixture
def systemic_error():
    from common import resilience

    class SystemicError(resilience.SYSTEMIC_ERRORS[0]):
        def __init__(self):
            Exception.__init__(self, "jaringan putus")

    return SystemicError

