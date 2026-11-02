import asyncio
import json
from types import SimpleNamespace

import pytest

from app.domains.clarifier import services


class FakeRedis:
    def __init__(self, cached=None, fail_push=False):
        self.cached, self.fail_push, self.pushed = cached or [], fail_push, []

    async def lrange(self, key, start, end):
        return self.cached

    async def rpush(self, key, *values):
        if self.fail_push:
            raise ConnectionError("redis mati")
        self.pushed.extend(json.loads(value) for value in values)

    async def ltrim(self, key, start, end):
        return None

    async def expire(self, key, seconds):
        return None


class FakeRepo:
    def __init__(self, stored=None):
        self.stored, self.added = stored or [], []

    async def get_session(self, session_id, student_id):
        return SimpleNamespace(id=session_id, classroom_id=1)

    async def get_recent_messages(self, session_id, limit):
        return self.stored

    async def add_message(self, session_id, role, content, **kwargs):
        self.added.append((role, content, kwargs))


class FakeDb:
    commits = 0

    async def commit(self):
        self.commits += 1


def message(role, content, content_markup=None):
    return SimpleNamespace(role=role, content=content, content_markup=content_markup)


def agent_result(**overrides):
    return {"status": "answered", "message": "bacaan", "scope": {"klass": "inti"}, "sources": [], "tool_calls": [], **overrides}


@pytest.fixture
def wiring(monkeypatch):
    seen = {}
    redis = FakeRedis()
    monkeypatch.setattr(services, "get_redis_client", lambda: redis)
    monkeypatch.setattr(services, "make_search_module_executor", lambda classroom, top_k: None)

    def run(question, history, executor):
        seen["history"] = history
        return seen["result"]

    monkeypatch.setattr(services.clarifier_agent, "run", run)
    return SimpleNamespace(seen=seen, redis=redis)


def ask(wiring, repo, result, redis=None):
    wiring.seen["result"] = result
    if redis is not None:
        wiring.redis.cached = redis.cached
    service = services.ChatbotService(repo, FakeDb())
    return asyncio.run(service.ask(1, 1, "Apa itu lingkaran?"))


def test_ask_menyimpan_bacaan_dan_markup_serta_mengirim_markup_ke_riwayat(wiring):
    repo = FakeRepo()
    ask(wiring, repo, agent_result(message="x pangkat dua", message_markup="$x^2$"))
    role, content, kwargs = repo.added[1]
    assert (role, content, kwargs["content_markup"]) == ("assistant", "x pangkat dua", "$x^2$")
    assert wiring.redis.pushed[-1] == {"role": "assistant", "content": "$x^2$"}


def test_ask_jawaban_tanpa_markup_menyimpan_none_dan_riwayat_memakai_bacaan(wiring):
    repo = FakeRepo()
    ask(wiring, repo, agent_result(message="teks biasa"))
    assert repo.added[1][2]["content_markup"] is None
    assert wiring.redis.pushed[-1] == {"role": "assistant", "content": "teks biasa"}


def test_riwayat_db_memakai_markup_bila_ada_dan_pesan_lama_memakai_bacaan(wiring):
    repo = FakeRepo(stored=[message("user", "tanya"), message("assistant", "bacaan baru", "$x$"), message("assistant", "pesan lama")])
    ask(wiring, repo, agent_result())
    assert wiring.seen["history"] == [
        {"role": "user", "content": "tanya"},
        {"role": "assistant", "content": "$x$"},
        {"role": "assistant", "content": "pesan lama"},
    ]


def test_kegagalan_redis_saat_menyimpan_riwayat_tidak_menggagalkan_jawaban(wiring):
    wiring.redis.fail_push = True
    repo = FakeRepo()
    result = ask(wiring, repo, agent_result())
    assert result["message"] == "bacaan"
    assert len(repo.added) == 2


def test_ask_menerima_hasil_agen_tanpa_kunci_markup(wiring):
    repo = FakeRepo()
    ask(wiring, repo, agent_result(status="out_of_scope"))
    assert repo.added[1][2]["content_markup"] is None
