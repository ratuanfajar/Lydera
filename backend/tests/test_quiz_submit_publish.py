import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.exceptions import BadRequestException
from app.domains.quizzer import services as quiz_services
from app.domains.quizzer.models.quiz_request import QuizRequestStatus
from app.domains.quizzer.schemas.soal_jawaban import SoalSubmitRequest


def run(coro):
    return asyncio.run(coro)


class FakeDb:
    def __init__(self):
        self.commits, self.rollbacks = 0, 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class Repo:
    def __init__(self, started_minutes_ago=5, duration=30, existing=None, quiz_status="done", end_in_minutes=120):
        now = datetime.now(timezone.utc)
        self.soal = SimpleNamespace(id=1, quiz_request_id=9, correct_option="B")
        self.progress = SimpleNamespace(is_done=False, started_at=now - timedelta(minutes=started_minutes_ago))
        self.quiz = SimpleNamespace(max_duration_minutes=duration, end_time=now + timedelta(minutes=end_in_minutes), status=quiz_status)
        self.existing, self.updated, self.created, self.published = existing, [], [], []

    async def get_soal_by_id(self, soal_id):
        return self.soal

    async def get_quiz_progress(self, quiz_id, student_id):
        return self.progress

    async def get_quiz_request(self, quiz_id):
        return self.quiz

    async def get_soal_jawaban(self, soal_id, student_id):
        return self.existing

    async def update_soal_jawaban(self, jawaban_id, selected_option, is_correct):
        self.updated.append((selected_option, is_correct))

    async def create_soal_jawaban(self, soal_id, student_id, selected_option, is_correct):
        self.created.append((selected_option, is_correct))

    async def validate_quiz_request(self, quiz_request_id, teacher_id, classroom_id):
        return True

    async def has_quiz_progress(self, quiz_request_id):
        return getattr(self, "started", False)

    async def update_quiz_status_publish(self, quiz_request_id, status, error=None):
        self.published.append(status)
        return True


def taking(repo, db=None):
    db = db or FakeDb()
    return quiz_services.QuizTakingService(progress_repo=repo, soal_repo=repo, quiz_repo=repo, db=db), db


def requests(repo, db=None):
    db = db or FakeDb()
    return quiz_services.QuizRequestService(repo, None, db, None), db


def submit(repo, **payload):
    service, _ = taking(repo)
    run(service.submit_answer(1, 7, SoalSubmitRequest(**payload)))


def test_langkah_tidak_dikirim_berarti_none_dan_kosong_berarti_hapus():
    assert SoalSubmitRequest(selected_option="A").langkah is None
    assert SoalSubmitRequest(selected_option="A", langkah=[]).langkah == []


def test_langkah_kosong_atau_spasi_dibuang_dan_sisanya_dirapikan():
    assert SoalSubmitRequest(selected_option="A", langkah=["  satu ", "", "   ", "dua"]).langkah == ["satu", "dua"]


def test_opsi_di_luar_a_sampai_d_ditolak():
    with pytest.raises(ValidationError):
        SoalSubmitRequest(selected_option="E")


def test_jawaban_pertama_disimpan_dengan_penilaian_kunci():
    repo = Repo()
    submit(repo, selected_option="B")
    assert repo.created == [("B", True)] and repo.updated == []


def test_kirim_ulang_mengganti_jawaban_tanpa_menambah_baris_baru():
    repo = Repo(existing=SimpleNamespace(id=3))
    submit(repo, selected_option="A")
    assert repo.updated == [("A", False)] and repo.created == []


def test_kirim_ulang_diikuti_jawaban_benar():
    repo = Repo(existing=SimpleNamespace(id=3))
    submit(repo, selected_option="A")
    submit(repo, selected_option="B")
    assert repo.updated == [("A", False), ("B", True)]


def test_submit_setelah_waktu_habis_ditolak_tetapi_dalam_masa_toleransi_diterima():
    late = Repo(started_minutes_ago=31)
    with pytest.raises(BadRequestException, match="Waktu pengerjaan"):
        submit(late, selected_option="A")
    assert late.created == [] and late.updated == []

    near = Repo()
    near.progress.started_at = datetime.now(timezone.utc) - timedelta(minutes=30) - timedelta(seconds=5)
    submit(near, selected_option="A")
    assert near.created


def test_submit_setelah_masa_toleransi_ditolak():
    repo = Repo()
    repo.progress.started_at = datetime.now(timezone.utc) - timedelta(minutes=30) - timedelta(seconds=11)
    with pytest.raises(BadRequestException, match="Waktu pengerjaan"):
        submit(repo, selected_option="A")
    assert repo.created == []


def test_submit_setelah_batas_akhir_kuis_ditolak_meski_durasi_belum_habis():
    repo = Repo(started_minutes_ago=5, duration=60, end_in_minutes=-1)
    with pytest.raises(BadRequestException, match="Waktu pengerjaan"):
        submit(repo, selected_option="A")


def test_submit_pada_sesi_selesai_tetap_ditolak():
    repo = Repo()
    repo.progress.is_done = True
    with pytest.raises(BadRequestException):
        submit(repo, selected_option="A")


@pytest.mark.parametrize("status", ["queued", "running", "failed"])
def test_kuis_yang_belum_selesai_dibuat_tidak_bisa_dipublikasikan(status):
    repo = Repo(quiz_status=status)
    service, _ = requests(repo)
    with pytest.raises(BadRequestException, match="belum selesai dibuat"):
        run(service.update_publish_status(1, 2, 9, QuizRequestStatus.PUBLISH))
    assert repo.published == []


def test_kuis_selesai_bisa_dipublikasikan_dan_dikembalikan_ke_draft_kapan_saja():
    repo = Repo(quiz_status="failed")
    service, _ = requests(repo)
    run(service.update_publish_status(1, 2, 9, QuizRequestStatus.DRAFT))
    repo.quiz.status = "done"
    run(service.update_publish_status(1, 2, 9, QuizRequestStatus.PUBLISH))
    assert repo.published == ["draft", "publish"]


def test_kuis_yang_sudah_dikerjakan_siswa_tidak_bisa_dikembalikan_ke_draft_tetapi_publish_ulang_boleh():
    repo = Repo()
    repo.started = True
    service, _ = requests(repo)
    with pytest.raises(BadRequestException, match="tidak dapat dikembalikan ke draft"):
        run(service.update_publish_status(1, 2, 9, QuizRequestStatus.DRAFT))
    run(service.update_publish_status(1, 2, 9, QuizRequestStatus.PUBLISH))
    assert repo.published == ["publish"]
