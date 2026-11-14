import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.exceptions import BadRequestException
from app.domains.quizzer import services as quiz_services
from app.domains.quizzer.models.quiz_request import QuizRequestStatus
from app.domains.quizzer.schemas.soal_edit_request import SoalEditRequest, StimulusEditRequest
from app.domains.quizzer.services import soal_service


def run(coro):
    return asyncio.run(coro)


class FakeDb:
    def __init__(self):
        self.commits, self.rollbacks = 0, 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def make_soal(soal_id, stimulus):
    return SimpleNamespace(
        id=soal_id, quiz_request_id=9, chapter_id=3, stimulus_id=stimulus.id, stimulus=stimulus, question_text="q", correct_option="A",
        kesimpulan="k", markup=None, review_status="pending", review_priority="normal", validation_notes=None,
        source_reading_order_start=0, source_reading_order_end=20,
        opsi=[SimpleNamespace(label=label, opsi_text=label) for label in "ABCD"],
        langkah=[SimpleNamespace(urutan=1, teks="l")],
    )


class QuizRepo:
    def __init__(self, stimulus, published=False, has_progress=False):
        self.stimulus = stimulus
        self.soal = [make_soal(1, stimulus), make_soal(2, stimulus)]
        self.updated = []
        self.quiz = SimpleNamespace(status_published=QuizRequestStatus.PUBLISH if published else QuizRequestStatus.DRAFT)
        self.has_progress = has_progress

    async def get_quiz_request(self, quiz_request_id):
        return self.quiz

    async def has_quiz_progress(self, quiz_request_id):
        return self.has_progress

    async def validate_soal_owner(self, soal_id, teacher_id):
        return True

    async def get_soal_by_id(self, soal_id):
        return next((s for s in self.soal if s.id == soal_id), None)

    async def get_stimulus_by_id(self, stimulus_id):
        return self.stimulus

    async def get_soal_by_stimulus(self, stimulus_id):
        return self.soal

    async def get_blocks_for_chapter(self, chapter_id):
        return [SimpleNamespace(reading_order=0, block_type="text", readable_text="materi")]

    async def update_stimulus_text(self, stimulus, readable_text, source_markup="", ringkasan=None, tabel=None, spesifikasi=None):
        self.updated.append((readable_text, source_markup, spesifikasi))
        stimulus.readable_text = readable_text
        stimulus.review_status = "edited"


def make_stimulus(jenis="teks", spesifikasi=None):
    return SimpleNamespace(id=7, chapter_id=3, jenis=jenis, spesifikasi=spesifikasi, readable_text="lama", source_markup="", review_status="pending")


def quiz_service(stimulus, monkeypatch, compute):
    repo, db = QuizRepo(stimulus), FakeDb()
    monkeypatch.setattr(soal_service.quizzer_regenerate, "compute_stimulus_edit", compute)
    return quiz_services.SoalService(repo, repo, db), repo, db


def test_stimulus_edit_request_butuh_tepat_satu_bentuk():
    with pytest.raises(ValidationError):
        StimulusEditRequest()
    with pytest.raises(ValidationError):
        StimulusEditRequest(source_markup="a", spesifikasi={"svg": "x"})
    assert StimulusEditRequest(spesifikasi={"svg": "x"}).narasi is None


def test_stimulus_edit_request_menolak_narasi_bersama_source_markup():
    with pytest.raises(ValidationError):
        StimulusEditRequest(source_markup="a", narasi="b")


def test_edit_stimulus_teks_menyimpan_dan_memperbarui_penanda_seluruh_cluster(monkeypatch):
    seen = {}

    def compute(rows, start, end, current, soal_list, edit):
        seen.update(current=current, edit=edit, ids=[s["id"] for s in soal_list])
        return {
            "new_stimulus": {"readable_text": "baru", "source_markup": "baru", "ringkasan": None, "tabel": None},
            "soal_issues": {1: [], 2: ["Opsi B juga benar."]},
        }

    service, repo, db = quiz_service(make_stimulus(), monkeypatch, compute)
    updated = run(service.edit_stimulus(1, 1, StimulusEditRequest(source_markup="baru")))
    assert seen["edit"] == {"source_markup": "baru"} and seen["ids"] == [1, 2]
    assert repo.updated == [("baru", "baru", None)] and db.commits == 1
    first, second = updated
    assert (first.review_status, first.review_priority) == ("edited", "normal")
    assert (second.review_priority, second.validation_notes) == ("high", "Opsi B juga benar.")


def test_edit_stimulus_bertipe_meneruskan_narasi_dan_spesifikasi(monkeypatch):
    seen = {}

    def compute(rows, start, end, current, soal_list, edit):
        seen.update(edit=edit, current=current)
        return {
            "new_stimulus": {"readable_text": "baru", "source_markup": "", "ringkasan": None, "tabel": None, "spesifikasi": {"svg": "<svg/>"}},
            "soal_issues": {},
        }

    service, repo, _ = quiz_service(make_stimulus("gambar", {"svg": "<svg/>"}), monkeypatch, compute)
    run(service.edit_stimulus(1, 1, StimulusEditRequest(narasi="Konteks.", spesifikasi={"svg": "<svg/>"})))
    assert seen["edit"] == {"narasi": "Konteks.", "spesifikasi": {"svg": "<svg/>"}} and seen["current"]["jenis"] == "gambar"
    assert repo.updated[0][2] == {"svg": "<svg/>"}


@pytest.mark.parametrize("jenis, spec, payload", [
    ("teks", None, StimulusEditRequest(spesifikasi={"svg": "x"})),
    ("gambar", {"svg": "x"}, StimulusEditRequest(source_markup="teks")),
])
def test_edit_stimulus_dengan_bentuk_tidak_cocok_jenis_ditolak(monkeypatch, jenis, spec, payload):
    service, repo, db = quiz_service(make_stimulus(jenis, spec), monkeypatch, lambda *args: pytest.fail("tidak boleh dihitung"))
    with pytest.raises(BadRequestException):
        run(service.edit_stimulus(1, 1, payload))
    assert repo.updated == [] and db.commits == 0


def test_edit_stimulus_tidak_valid_tidak_menyimpan_apa_pun(monkeypatch):
    def compute(*args):
        raise ValueError("Gambar tidak dapat dirender: path rusak")

    service, repo, db = quiz_service(make_stimulus("gambar", {"svg": "x"}), monkeypatch, compute)
    with pytest.raises(BadRequestException, match="tidak dapat dirender"):
        run(service.edit_stimulus(1, 1, StimulusEditRequest(spesifikasi={"svg": "y"})))
    assert repo.updated == [] and db.commits == 0


def test_edit_stimulus_pada_soal_tanpa_stimulus_ditolak(monkeypatch):
    service, repo, _ = quiz_service(make_stimulus(), monkeypatch, lambda *args: {})
    repo.soal[0].stimulus_id = None
    with pytest.raises(BadRequestException):
        run(service.edit_stimulus(1, 1, StimulusEditRequest(source_markup="x")))


@pytest.mark.xfail(
    strict=True,
    reason="spec 0008 §1: PATCH soal harus menerima soal berstimulus; kode masih menolaknya di soal_service.edit_soal",
)
def test_edit_soal_hots_tidak_lagi_ditolak_dan_diverifikasi_ulang(monkeypatch):
    service, repo, db = quiz_service(make_stimulus(), monkeypatch, lambda *args: {})
    monkeypatch.setattr(soal_service.quizzer_regenerate, "review_soal", lambda source, soal, stimulus_text: ["Langkah tidak valid."])
    result = run(service.edit_soal(1, 1, SoalEditRequest(correct_option="B")))
    assert result.correct_option == "B" and result.review_status == "edited"
    assert (result.review_priority, result.validation_notes) == ("high", "Langkah tidak valid.")


def test_edit_soal_dengan_notasi_mentah_di_luar_rumus_ditolak(monkeypatch):
    service, repo, db = quiz_service(make_stimulus(), monkeypatch, lambda *args: {})
    repo.soal[0].stimulus_id = None
    with pytest.raises(BadRequestException, match="Markup tidak valid"):
        run(service.edit_soal(1, 1, SoalEditRequest(question_text="Berapa x = 3 + 2?")))
    assert db.commits == 0


@pytest.mark.parametrize("published, has_progress", [(True, False), (False, True)])
def test_soal_stimulus_dan_regenerasi_terkunci_bila_kuis_dipublikasikan_atau_sudah_dikerjakan(monkeypatch, published, has_progress):
    service, repo, db = quiz_service(make_stimulus(), monkeypatch, lambda *args: pytest.fail("tidak boleh dihitung"))
    repo.quiz.status_published = QuizRequestStatus.PUBLISH if published else QuizRequestStatus.DRAFT
    repo.has_progress = has_progress
    for call in (
        service.edit_soal(1, 1, SoalEditRequest(correct_option="B")),
        service.edit_stimulus(1, 1, StimulusEditRequest(source_markup="baru")),
        service.regenerate_cluster(1, 1, "perbaiki"),
    ):
        with pytest.raises(BadRequestException):
            run(call)
    assert repo.updated == [] and db.commits == 0
