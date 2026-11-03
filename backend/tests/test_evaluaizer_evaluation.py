import asyncio
from types import SimpleNamespace

import pytest
from redis.exceptions import LockNotOwnedError, RedisError

from app.domains.evaluaizer import evaluation, services


class FakeRepo:
    def __init__(self, soal_list, jawaban_list):
        self.soal_list, self.jawaban_list = soal_list, jawaban_list
        self.saved = []

    async def get_soal_for_request(self, quiz_request_id):
        return self.soal_list

    async def get_jawaban_for_request(self, quiz_request_id, student_id):
        return self.jawaban_list

    async def get_blocks_for_chapter(self, chapter_id):
        return [SimpleNamespace(reading_order=10, block_type="text", readable_text="Materi sumber.")]

    async def save_evaluation(self, jawaban, evaluation_data):
        self.saved.append((jawaban.id, evaluation_data["langkah_ke"]))
        jawaban.evaluated_at = "sudah"


class FakeDb:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        raise AssertionError("rollback tidak boleh terjadi")


class FakeLock:
    def __init__(self, free, expired=False):
        self.free, self.expired, self.released = free, expired, False

    async def acquire(self, blocking=False):
        assert blocking is False
        return self.free

    async def release(self):
        self.released = True
        if self.expired:
            raise LockNotOwnedError("kedaluwarsa")


class FakeRedis:
    def __init__(self, lock, store=None):
        self.fake_lock, self.names, self.store = lock, [], store if store is not None else {}

    async def exists(self, key):
        return int(key in self.store)

    async def set(self, key, value, ex=None):
        self.store[key] = (value, ex)

    def lock(self, name, timeout):
        self.names.append((name, timeout))
        return self.fake_lock


class BrokenRedis(FakeRedis):
    async def exists(self, key):
        raise RedisError("putus")

    async def set(self, key, value, ex=None):
        raise RedisError("putus")


def make_soal(id, question="Soal?"):
    return SimpleNamespace(
        id=id,
        chapter_id=1,
        source_reading_order_start=10,
        source_reading_order_end=10,
        question_text=question,
        opsi=[SimpleNamespace(label="A", opsi_text="a"), SimpleNamespace(label="B", opsi_text="b")],
        correct_option="A",
        kesimpulan="Jadi a.",
        langkah=[SimpleNamespace(urutan=1, teks="Langkah kunci.")],
        stimulus=None,
    )


def make_jawaban(id, soal_id=None, correct=False, evaluated=None, steps=1, determinable=None, step=None):
    return SimpleNamespace(
        id=id,
        soal_id=soal_id or id,
        is_correct=correct,
        selected_option="B",
        evaluated_at=evaluated,
        langkah=[SimpleNamespace(urutan=n, teks="Langkah siswa.") for n in range(1, steps + 1)],
        divergence_step=step,
        diagnosis="Keterangan." if determinable is not None else None,
        letak_kutipan="Langkah siswa." if step else None,
        letak_dapat_ditentukan=determinable,
        needs_review=False,
    )


def fake_evaluate(source, stimulus, question, options, correct, key, conclusion, student_option, student_steps):
    if question == "gagal":
        raise RuntimeError("LLM gagal")
    if question == "permanen":
        raise ValueError("tidak menghasilkan poin")
    return {
        "dapat_ditentukan": True, "langkah_ke": 1, "kutipan": "Langkah siswa.", "keterangan": "k",
        "needs_review": False, "issues": [],
    }


@pytest.fixture(autouse=True)
def stub_llm(monkeypatch):
    monkeypatch.setattr(evaluation.evaluaizer_evaluate, "evaluate_scratchwork", fake_evaluate)


def run_evaluation(repo, redis, db=None):
    evaluator = evaluation.AnswerEvaluator(repo, db or FakeDb(), redis)
    return asyncio.run(evaluator.evaluate(7, 9))


@pytest.fixture
def mixed_repo():
    return FakeRepo([make_soal(1), make_soal(2, "gagal"), make_soal(3)], [make_jawaban(11, 1), make_jawaban(12, 2), make_jawaban(13, 3, correct=True)])


def test_evaluate_menyimpan_yang_berhasil_dan_mencatat_yang_gagal(mixed_repo):
    db, lock = FakeDb(), FakeLock(free=True)
    redis = FakeRedis(lock)
    outcome = run_evaluation(mixed_repo, redis, db)
    assert outcome.failed == {12}
    assert outcome.busy is False
    assert mixed_repo.saved == [(11, 1)]
    assert db.commits == 2
    assert lock.released
    assert redis.names == [("evaluaizer_lock:7:9", evaluation.LOCK_SECONDS)]


def test_evaluate_kegagalan_sementara_diberi_cooldown_singkat(mixed_repo):
    redis = FakeRedis(FakeLock(free=True))
    run_evaluation(mixed_repo, redis)
    assert redis.store == {"evaluaizer_failed:12": (1, evaluation.TRANSIENT_FAILURE_COOLDOWN_SECONDS)}


def test_evaluate_melewati_jawaban_yang_masih_cooldown(mixed_repo, monkeypatch):
    store = {"evaluaizer_failed:12": (1, 45)}
    calls = []
    monkeypatch.setattr(evaluation.evaluaizer_evaluate, "evaluate_scratchwork", lambda *args: calls.append(args))
    repo = FakeRepo([make_soal(2, "gagal")], [make_jawaban(12, 2)])
    outcome = run_evaluation(repo, FakeRedis(FakeLock(free=True), store))
    assert outcome.failed == {12}
    assert calls == []


def test_evaluate_kegagalan_permanen_diberi_cooldown_panjang():
    repo = FakeRepo([make_soal(4, "permanen")], [make_jawaban(14, 4)])
    store = {}
    run_evaluation(repo, FakeRedis(FakeLock(free=True), store))
    assert store == {"evaluaizer_failed:14": (1, evaluation.PERMANENT_FAILURE_COOLDOWN_SECONDS)}


def test_evaluate_tetap_jalan_saat_redis_cooldown_putus():
    repo = FakeRepo([make_soal(1), make_soal(2, "gagal")], [make_jawaban(31, 1), make_jawaban(32, 2)])
    db = FakeDb()
    outcome = run_evaluation(repo, BrokenRedis(FakeLock(free=True)), db)
    assert outcome.failed == {32}
    assert repo.saved == [(31, 1)]
    assert db.commits == 2


def test_evaluate_lock_terpakai_menandai_busy_tanpa_menyimpan(mixed_repo):
    db, lock = FakeDb(), FakeLock(free=False)
    outcome = run_evaluation(mixed_repo, FakeRedis(lock), db)
    assert outcome.busy is True
    assert outcome.failed == set()
    assert mixed_repo.saved == []
    assert db.commits == 0
    assert not lock.released


def test_evaluate_lock_kedaluwarsa_saat_dilepas_tidak_menggagalkan():
    expired = FakeLock(free=True, expired=True)
    repo = FakeRepo([make_soal(1)], [make_jawaban(21, 1, evaluated="x", determinable=True, step=1)])
    outcome = run_evaluation(repo, FakeRedis(expired))
    assert outcome.busy is False
    assert expired.released


@pytest.mark.parametrize(
    ("jawaban", "expected"),
    [
        (make_jawaban(1), True),
        (make_jawaban(2, correct=True), False),
        (make_jawaban(3, steps=0), False),
        (make_jawaban(4, evaluated="x", determinable=True, step=1), False),
        (make_jawaban(5, correct=True, steps=0), False),
    ],
)
def test_needs_evaluation_hanya_untuk_jawaban_salah_yang_punya_langkah_dan_belum_dievaluasi(jawaban, expected):
    assert evaluation.needs_evaluation(jawaban) is expected


@pytest.mark.parametrize(
    "jawaban",
    [None, make_jawaban(5, correct=True, evaluated="x", determinable=True), make_jawaban(6), make_jawaban(7, steps=0)],
)
def test_letak_kesalahan_kosong_untuk_jawaban_benar_tanpa_langkah_atau_belum_dievaluasi(jawaban):
    assert services._letak_kesalahan(jawaban) is None


def test_letak_kesalahan_membawa_langkah_kutipan_dan_keterangan():
    result = services._letak_kesalahan(make_jawaban(8, evaluated="x", determinable=True, step=2))
    assert (result.dapat_ditentukan, result.langkah_ke, result.kutipan, result.keterangan) == (True, 2, "Langkah siswa.", "Keterangan.")


def test_letak_kesalahan_tidak_dapat_ditentukan_tanpa_langkah_dan_kutipan():
    result = services._letak_kesalahan(make_jawaban(9, evaluated="x", determinable=False))
    assert result.dapat_ditentukan is False and result.langkah_ke is None and result.kutipan is None


def test_jawaban_salah_tanpa_langkah_tidak_memanggil_model(monkeypatch):
    calls = []
    monkeypatch.setattr(evaluation.evaluaizer_evaluate, "evaluate_scratchwork", lambda *args: calls.append(args))
    repo = FakeRepo([make_soal(1)], [make_jawaban(41, 1, steps=0)])
    outcome = run_evaluation(repo, FakeRedis(FakeLock(free=True)))
    assert calls == [] and outcome.failed == set() and repo.saved == []


def test_evaluation_arguments_menyusun_sumber_opsi_dan_langkah():
    blocks = [{"reading_order": 10, "block_type": "text", "readable_text": "Materi sumber."}]
    args = evaluation._evaluation_arguments(make_soal(1), make_jawaban(9), blocks)
    assert args[0] == "Materi sumber."
    assert args[3] == {"A": "a", "B": "b"}
    assert args[5] == ["Langkah kunci."]
    assert args[8] == ["Langkah siswa."]
