import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.exceptions import BadRequestException
from app.domains.contents.schemas.blocks.block_edit import BlockEditRequest
from app.domains.contents.services import block_service


def run(coro):
    return asyncio.run(coro)


def test_block_edit_request_butuh_minimal_satu_isi():
    with pytest.raises(ValidationError):
        BlockEditRequest()
    assert BlockEditRequest(readable_text="x").readable_text == "x"


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

    monkeypatch.setattr(block_service, "enqueue_chapter_progress_reset_job", reset)

    def make(target):
        repo = BlockRepo(target)
        return block_service.BlockService(repo, None), repo, resets

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
    monkeypatch.setattr(block_service.annoter_regenerate.math_text, "readable_texts", lambda markups, issues=None: ["x kuadrat"])
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


@pytest.mark.parametrize("text", ["**tebal**", "# judul", "x^2 sama dengan empat"])
def test_edit_blok_teks_dengan_markdown_atau_notasi_mentah_ditolak(content_service, text):
    service, repo, _ = content_service(block("text"))
    with pytest.raises(BadRequestException):
        run(service.edit_block(5, 1, BlockEditRequest(readable_text=text)))
    assert repo.updates == []
