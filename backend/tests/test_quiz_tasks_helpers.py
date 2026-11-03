import pytest

from app.tasks import quiz_tasks


def report(**overrides):
    chapter = {
        "chapter_id": 4, "skipped_reason": None, "failed": [],
        "generated": {"lots": 2, "hots": 1},
    }
    base = {"chapters": [{**chapter, **overrides}], "summary": {"generated": 3, "failed": 0}}
    return base


def item(level=3, stimulus=None):
    return {
        "chapter_id": 4, "level": level, "source_point": "Poin materi. " * 20, "review_priority": "high",
        "validation_notes": "catatan",
        "data": {
            "bloom_level": level, "question_text": "Soal?", "correct_option": "B",
            "options": {"A": "a", "B": "b", "C": "c", "D": "d"}, "langkah": ["l1"], "kesimpulan": "k",
            "reading_order_start": 10, "reading_order_end": 30, "stimulus": stimulus, "markup": {"question": "$x$"},
        },
    }


def test_pesan_selesai_tanpa_kegagalan():
    assert quiz_tasks._done_message(5, report()) == "Berhasil membuat dan menyimpan 5 soal."


def test_pesan_selesai_menyebut_soal_gagal_dan_bab_dilewati():
    data = report(skipped_reason="kosong")
    data["summary"]["failed"] = 2
    message = quiz_tasks._done_message(3, data)
    assert message == "Berhasil membuat dan menyimpan 3 soal. 2 soal gagal dibuat, 1 bab dilewati; lihat laporan cakupan."


def test_ringkasan_kegagalan_memuat_alasan_bab_dan_maksimal_tiga_slot_per_bab():
    failed = [{"level": level, "point": "p", "error": "Layanan model tidak tersedia."} for level in (1, 2, 3, 4)]
    summary = quiz_tasks._failure_summary(report(skipped_reason="Bab tidak memiliki teks.", failed=failed))
    assert "Bab 4: Bab tidak memiliki teks." in summary
    assert summary.count("Layanan model tidak tersedia.") == 3
    assert "level C4" not in summary


def test_ringkasan_kegagalan_dipotong_seribu_karakter():
    failed = [{"level": 1, "point": "p", "error": "x" * 1200}]
    assert len(quiz_tasks._failure_summary(report(failed=failed))) == 1000


@pytest.mark.parametrize("level, group", [(2, "lots"), (5, "hots")])
def test_penanda_gagal_konversi_memindahkan_hitungan_dari_berhasil_ke_gagal(level, group):
    data = report()
    quiz_tasks._mark_conversion_failure(data, item(level))
    assert data["chapters"][0]["generated"][group] == (1 if group == "lots" else 0)
    assert data["summary"] == {"generated": 2, "failed": 1}
    assert data["chapters"][0]["failed"][0]["error"] == "Data soal tidak dapat disimpan."
    assert len(data["chapters"][0]["failed"][0]["point"]) == 120


def test_konversi_soal_tanpa_stimulus():
    request = quiz_tasks._to_soal_create_request(item())
    assert request.chapter_id == 4 and request.data.stimulus is None
    assert (request.review_priority, request.validation_notes, request.data.markup) == ("high", "catatan", {"question": "$x$"})


def test_konversi_soal_dengan_stimulus_membawa_tabel_dan_markup():
    stimulus = {"readable_text": "teks", "source_markup": "$x$", "ringkasan": "ring", "tabel": {"kolom": ["a"], "baris": [["1"]]}}
    request = quiz_tasks._to_soal_create_request(item(5, stimulus))
    assert request.data.stimulus.readable_text == "teks" and request.data.stimulus.tabel == stimulus["tabel"]
    assert request.data.stimulus.source_markup == "$x$" and request.data.stimulus.ringkasan == "ring"


def test_konversi_soal_data_hilang_melempar_error():
    broken = item()
    del broken["data"]["question_text"]
    with pytest.raises(KeyError):
        quiz_tasks._to_soal_create_request(broken)


def test_konversi_stimulus_bertipe_membawa_jenis_dan_spesifikasi():
    spec = {"bangun": "kubus", "ukuran": {"rusuk": 4}, "skema_versi": 1}
    request = quiz_tasks._to_soal_create_request(item(5, {"readable_text": "teks", "jenis": "gambar", "spesifikasi": spec}))
    assert request.data.stimulus.jenis == "gambar" and request.data.stimulus.spesifikasi == spec


def test_konversi_stimulus_teks_berjenis_teks_tanpa_spesifikasi():
    request = quiz_tasks._to_soal_create_request(item(5, {"readable_text": "teks"}))
    assert request.data.stimulus.jenis == "teks" and request.data.stimulus.spesifikasi is None
