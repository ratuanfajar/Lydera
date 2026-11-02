from types import SimpleNamespace

from app.tasks import mineru_tasks


def test_pesan_selesai_tanpa_kegagalan():
    report = SimpleNamespace(needs_review=0)
    assert mineru_tasks.completion_message(12, report) == "Successfully processed 12 blocks."


def test_pesan_selesai_menyebut_jumlah_blok_yang_perlu_ditinjau():
    report = SimpleNamespace(needs_review=3)
    message = mineru_tasks.completion_message(12, report)
    assert message.startswith("Successfully processed 12 blocks.")
    assert "3 blok atau window gagal" in message
