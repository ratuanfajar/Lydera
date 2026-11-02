import os

for name in ("SEARCH_API_KEY", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "EMBEDDING_API_KEY"):
    os.environ[name] = ""
