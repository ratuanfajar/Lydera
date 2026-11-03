import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.exceptions import BadRequestException
from app.domains.contents import services as content_services
from app.domains.contents.schemas.blocks.block_edit import BlockEditRequest
from app.domains.quizzer import services as quiz_services
from app.domains.quizzer.schemas.soal_edit_request import StimulusEditRequest


class FakeDb:
    def __init__(self):
        self.commits, self.rollbacks = 0, 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def run(coro):
    return asyncio.run(coro)


def test_block_edit_request_butuh_minimal_satu_isi():
    with pytest.raises(ValidationError):
        BlockEditRequest()
    assert BlockEditRequest(readable_text="x").readable_text == "x"


def test_stimulus_edit_request_butuh_tepat_satu_bentuk():
    with pytest.raises(ValidationError):
        StimulusEditRequest()
    with pytest.raises(ValidationError):
        StimulusEditRequest(source_markup="a", spesifikasi={"svg": "x"})
    assert StimulusEditRequest(spesifikasi={"svg": "x"}).narasi is None


class BlockRepo:
    def __init__(self, block):
        self.block, self.updates = block, []

    async def get_teacher_blocks(self, block_ids, teacher_id):
        return [self.block]

    async def bulk_update_readable_text(self, update_data):
        self.updates.append(update_data)
        return True


def block(block_type, **extra):
    base = dict(id=5, chapter_id=9, block_type=block_type, readable_text="lama", source_markup=None, ringkasan=None, tabel=None)
    return SimpleNamespace(**{**base, **extra})


@pytest.fixture
def content_service(monkeypatch):
    resets = []

    async def reset(chapter_id):
        resets.append(chapter_id)

    monkeypatch.setattr(content_services, "enqueue_chapter_progress_reset_job", reset)

    def make(target):
        repo = BlockRepo(target)
        return content_services.ContentService(repo, None, None), repo, resets

    return make


def test_edit_blok_gambar_memakai_readable_text_guru_dan_mereset_progres(content_service):
    service, repo, resets = content_service(block("image"))
    result = run(service.edit_block(5, 1, BlockEditRequest(readable_text="Grafik naik dari kiri ke kanan.")))
    assert result.readable_text == "Grafik naik dari kiri ke kanan." and result.review_priority == "normal"
    assert repo.updates == [[{"id": 5, "readable_text": "Grafik naik dari kiri ke kanan.", "review_priority": "normal"}]]
    assert resets == [9]


def test_edit_blok_tabel_menurunkan_ulang_bacaan_ringkasan_dan_html(content_service):
    service, repo, _ = content_service(block("table"))
    tabel = {"judul": "Nilai", "kolom": ["x", "y"], "baris": [["1", "2"]]}
    result = run(service.edit_block(5, 1, BlockEditRequest(tabel=tabel)))
    assert "Ada 2 kolom" in result.readable_text and result.ringkasan and result.tabel["kolom"] == ["x", "y"]
    assert "<table" in repo.updates[0][0]["source_markup"]


def test_edit_blok_rumus_dari_sumber_memakai_verbalizer(content_service, monkeypatch):
    monkeypatch.setattr(content_services.annoter_regenerate.math_text, "readable_texts", lambda markups, issues=None: ["x kuadrat"])
    service, repo, _ = content_service(block("formula"))
    result = run(service.edit_block(5, 1, BlockEditRequest(source_markup="x^{2}")))
    assert result.readable_text == "x kuadrat" and repo.updates[0][0]["source_markup"] == "x^{2}"


@pytest.mark.parametrize("block_type, payload", [
    ("image", BlockEditRequest(readable_text="**tebal**")),
    ("formula", BlockEditRequest(readable_text="x^2 sama dengan empat")),
    ("table", BlockEditRequest(tabel={"judul": "t", "kolom": ["a", "b"], "baris": [["1"]]})),
    ("image", BlockEditRequest(source_markup="x")),
])
def test_edit_blok_tidak_valid_ditolak_tanpa_menyimpan(content_service, block_type, payload):
    service, repo, resets = content_service(block(block_type))
    with pytest.raises(BadRequestException):
        run(service.edit_block(5, 1, payload))
    assert repo.updates == [] and resets == []


def test_edit_blok_teks_menyimpan_apa_adanya_dan_menolak_kosong(content_service):
    service, repo, _ = content_service(block("text"))
    run(service.edit_block(5, 1, BlockEditRequest(readable_text="  Kalimat dari buku.  ")))
    assert repo.updates[0][0]["readable_text"] == "Kalimat dari buku."
    with pytest.raises(BadRequestException):
        run(service.edit_block(5, 1, BlockEditRequest(source_markup="x")))


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
        self.quiz = SimpleNamespace(status_published=quiz_services.QuizRequestStatus.PUBLISH if published else quiz_services.QuizRequestStatus.DRAFT)
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
    monkeypatch.setattr(quiz_services.quizzer_regenerate, "compute_stimulus_edit", compute)
    return quiz_services.QuizService(repo, db, None), repo, db


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


def test_edit_soal_hots_tidak_lagi_ditolak_dan_diverifikasi_ulang(monkeypatch):
    from app.domains.quizzer.schemas.soal_edit_request import SoalEditRequest

    service, repo, db = quiz_service(make_stimulus(), monkeypatch, lambda *args: {})
    monkeypatch.setattr(quiz_services.quizzer_regenerate, "review_soal", lambda source, soal, stimulus_text: ["Langkah tidak valid."])
    result = run(service.edit_soal(1, 1, SoalEditRequest(correct_option="B")))
    assert result.correct_option == "B" and result.review_status == "edited"
    assert (result.review_priority, result.validation_notes) == ("high", "Langkah tidak valid.")


@pytest.mark.parametrize("text", ["**tebal**", "# judul", "x^2 sama dengan empat"])
def test_edit_blok_teks_dengan_markdown_atau_notasi_mentah_ditolak(content_service, text):
    service, repo, _ = content_service(block("text"))
    with pytest.raises(BadRequestException):
        run(service.edit_block(5, 1, BlockEditRequest(readable_text=text)))
    assert repo.updates == []


def test_stimulus_edit_request_menolak_narasi_bersama_source_markup():
    with pytest.raises(ValidationError):
        StimulusEditRequest(source_markup="a", narasi="b")


def test_edit_soal_dengan_notasi_mentah_di_luar_rumus_ditolak(monkeypatch):
    from app.domains.quizzer.schemas.soal_edit_request import SoalEditRequest

    service, repo, db = quiz_service(make_stimulus(), monkeypatch, lambda *args: {})
    with pytest.raises(BadRequestException):
        run(service.edit_soal(1, 1, SoalEditRequest(question_text="Berapa x = 3 + 2?")))
    assert db.commits == 0


@pytest.mark.parametrize("published, has_progress", [(True, False), (False, True)])
def test_soal_stimulus_dan_regenerasi_terkunci_bila_kuis_dipublikasikan_atau_sudah_dikerjakan(monkeypatch, published, has_progress):
    from app.domains.quizzer.schemas.soal_edit_request import SoalEditRequest

    service, repo, db = quiz_service(make_stimulus(), monkeypatch, lambda *args: pytest.fail("tidak boleh dihitung"))
    repo.quiz.status_published = quiz_services.QuizRequestStatus.PUBLISH if published else quiz_services.QuizRequestStatus.DRAFT
    repo.has_progress = has_progress
    for call in (
        service.edit_soal(1, 1, SoalEditRequest(correct_option="B")),
        service.edit_stimulus(1, 1, StimulusEditRequest(source_markup="baru")),
        service.regenerate_cluster(1, 1, "perbaiki"),
    ):
        with pytest.raises(BadRequestException):
            run(call)
    assert repo.updated == [] and db.commits == 0
