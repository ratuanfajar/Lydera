from __future__ import annotations

import re

MAX_TOKENS = 12
MIN_TOKEN_CHARS = 3

STOPWORDS = frozenset(
    "yang dan atau dengan untuk pada dari dalam adalah itu ini apa apakah bagaimana mengapa kenapa siapa kapan dimana "
    "jika maka agar bila saat sebuah suatu para oleh akan bisa dapat ada tidak bukan saya aku kamu kita mereka nya lalu "
    "juga serta tetapi namun karena sama sudah belum masih lebih sangat cara tolong jelaskan sebutkan".split()
)

_TOKEN = re.compile(r"[a-z0-9]+")


def lexical_tokens(question: str) -> list[str]:
    tokens: list[str] = []
    for token in _TOKEN.findall(question.lower()):
        if len(token) >= MIN_TOKEN_CHARS and token not in STOPWORDS and token not in tokens:
            tokens.append(token)
    return tokens[:MAX_TOKENS]

