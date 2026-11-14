import asyncio
from types import SimpleNamespace

from app.domains.contents.services import block_service


class FakeRepo:
    def __init__(self, neighbors):
        self.neighbors, self.asked = neighbors, []

    async def get_neighbor_blocks(self, chapter_id, reading_order):
        self.asked.append((chapter_id, reading_order))
        return self.neighbors


def block(block_type, text, reading_order):
    return SimpleNamespace(block_type=block_type, readable_text=text, reading_order=reading_order)


def context_for(neighbors):
    repo = FakeRepo(neighbors)
    service = block_service.BlockService(repo, None)
    image = SimpleNamespace(chapter_id=7, reading_order=30)
    return asyncio.run(service._image_context(image)), repo


def test_konteks_gambar_menggabungkan_teks_dan_heading_tetangga():
    text, repo = context_for([block("text", "Sebelum gambar.", 20), block("heading", "Sesudah", 40)])
    assert text == "Sebelum gambar. Sesudah"
    assert repo.asked == [(7, 30)]


def test_konteks_gambar_mengabaikan_tetangga_bukan_teks_dan_kosong():
    text, _ = context_for([block("image", "gambar lain", 20), block("text", "", 40)])
    assert text == ""


def test_konteks_gambar_mengambil_ekor_blok_sebelum_dan_kepala_blok_sesudah():
    limit = block_service.annoter_regenerate.IMAGE_CONTEXT_CHARS
    before = "x" * 1000 + "AKHIR"
    after = "AWAL" + "y" * 1000
    text, _ = context_for([block("text", before, 20), block("text", after, 40)])
    parts = text.split(" ")
    assert parts[0].endswith("AKHIR") and len(parts[0]) == limit
    assert parts[1].startswith("AWAL") and len(parts[1]) == limit
