import asyncio

import pytest

from app.domains.quizzer import services as quiz_services
from app.domains.quizzer.schemas.step_request import AddStepRequest


class FakeDb:
    def __init__(self):
        self.commits, self.rollbacks = 0, 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class StepRepo:
    def __init__(self, can_remove=True, fail=None):
        self.added, self.removed = [], []
        self.can_remove, self.fail = can_remove, fail

    async def add_step(self, soal_id, student_id, step):
        if self.fail == "add":
            raise RuntimeError("gagal menyimpan langkah")
        self.added.append((soal_id, student_id, step))
        return {"id": 11, "urutan": 1, "teks": step}

    async def remove_step(self, step_id, student_id):
        if self.fail == "remove":
            raise RuntimeError("gagal menghapus langkah")
        self.removed.append((step_id, student_id))
        return self.can_remove


def service(repo, db):
    return quiz_services.QuizTakingService(progress_repo=repo, soal_repo=repo, quiz_repo=repo, db=db)


def test_langkah_baru_disimpan_dan_di_commit():
    repo, db = StepRepo(), FakeDb()
    result = asyncio.run(service(repo, db).add_step(AddStepRequest(step="2 + 3"), 1, 7))
    assert repo.added == [(1, 7, "2 + 3")]
    assert (result.id, result.steps, result.text) == (11, 1, "2 + 3")
    assert (db.commits, db.rollbacks) == (1, 0)


def test_langkah_gagal_disimpan_di_rollback():
    repo, db = StepRepo(fail="add"), FakeDb()
    with pytest.raises(RuntimeError):
        asyncio.run(service(repo, db).add_step(AddStepRequest(step="x"), 1, 7))
    assert (db.commits, db.rollbacks) == (0, 1)


def test_langkah_milik_siswa_dihapus_dan_di_commit():
    repo, db = StepRepo(), FakeDb()
    assert asyncio.run(service(repo, db).delete_step(11, 7)) is True
    assert repo.removed == [(11, 7)]
    assert (db.commits, db.rollbacks) == (1, 0)


def test_langkah_bukan_milik_siswa_tidak_dihapus_dan_tidak_di_commit():
    repo, db = StepRepo(can_remove=False), FakeDb()
    assert asyncio.run(service(repo, db).delete_step(11, 8)) is False
    assert (db.commits, db.rollbacks) == (0, 1)


def test_penghapusan_langkah_gagal_di_rollback():
    repo, db = StepRepo(fail="remove"), FakeDb()
    with pytest.raises(RuntimeError):
        asyncio.run(service(repo, db).delete_step(11, 7))
    assert (db.commits, db.rollbacks) == (0, 1)
