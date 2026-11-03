import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.core.exceptions import BadRequestException, NotFoundException, TooManyRequestException
from app.domains.clarifier import services


class FakeRedis:
    def __init__(self, cached=None, fail_push=False):
        self.cached, self.fail_push, self.pushed, self.kv = cached or [], fail_push, [], {}

    async def get(self, key):
        return self.kv.get(key)

    async def set(self, key, value, ex=None):
        self.kv[key] = value

    async def incr(self, key):
        self.kv[key] = int(self.kv.get(key, 0)) + 1
        return self.kv[key]

    async def getdel(self, key):
        return self.kv.pop(key, None)

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
    def __init__(self, stored=None, active=None):
        self.stored, self.added, self.active = stored or [], [], active or []

    async def get_started_unfinished_quizzes(self, classroom_id, student_id):
        return self.active

    async def get_visual_blocks_for_references(self, classroom_id, references):
        self.asked_references = references
        return getattr(self, "visual", {})

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


def quiz_row(started_minutes_ago, duration=30, end_in_minutes=120):
    now = datetime.now(timezone.utc)
    progress = SimpleNamespace(started_at=now - timedelta(minutes=started_minutes_ago))
    quiz = SimpleNamespace(max_duration_minutes=duration, end_time=now + timedelta(minutes=end_in_minutes))
    return progress, quiz


def test_ask_ditolak_saat_siswa_sedang_mengerjakan_kuis(wiring):
    repo = FakeRepo(active=[quiz_row(started_minutes_ago=5)])
    with pytest.raises(BadRequestException, match="kuis sedang berlangsung"):
        ask(wiring, repo, agent_result())
    assert repo.added == []


@pytest.mark.parametrize("row", [quiz_row(started_minutes_ago=31), quiz_row(started_minutes_ago=5, duration=60, end_in_minutes=-1)])
def test_ask_boleh_bila_waktu_kuis_sudah_habis_walau_belum_ditandai_selesai(wiring, row):
    repo = FakeRepo(active=[row])
    assert ask(wiring, repo, agent_result())["message"] == "bacaan"


def test_ask_boleh_tanpa_kuis_aktif(wiring):
    repo = FakeRepo(active=[])
    assert ask(wiring, repo, agent_result())["message"] == "bacaan"


def source(reference, **overrides):
    return {"source_type": "modul", "label": "Bab", "reference": reference, "evidence": "e", "justification": "j", "verified": True, **overrides}


def visual_block(block_id, block_type, **extra):
    base = dict(id=block_id, chapter_id=4, block_type=block_type, readable_text="Deskripsi.", caption=None, ringkasan=None, tabel=None, image_file=None)
    return SimpleNamespace(**{**base, **extra})


def test_sumber_modul_terverifikasi_membawa_blok_tabel_dan_gambar_asli(wiring):
    repo = FakeRepo()
    repo.visual = {7: [visual_block(8, "table", tabel={"judul": "t", "kolom": ["a"], "baris": [["1"]]}, ringkasan="Ringkasan."), visual_block(9, "image", image_file="a.png")]}
    result = ask(wiring, repo, agent_result(sources=[source("7"), source("12", verified=False), source("http://x", source_type="oer")]))
    assert repo.asked_references == [7]
    table, image = result["sources"][0]["blok"]
    assert table["block_type"] == "table" and table["tabel"]["judul"] == "t" and table["image_url"] is None
    assert image["image_url"].endswith("/static/annotations/4/raw-4/auto/images/a.png")
    assert "blok" not in result["sources"][1] and "blok" not in result["sources"][2]


def test_kegagalan_membaca_blok_sumber_tidak_menggagalkan_jawaban(wiring):
    repo = FakeRepo()

    async def broken(classroom_id, references):
        raise RuntimeError("db putus")

    repo.get_visual_blocks_for_references = broken
    result = ask(wiring, repo, agent_result(sources=[source("7")]))
    assert result["message"] == "bacaan" and "blok" not in result["sources"][0]


def test_tanpa_sumber_modul_tidak_membaca_blok(wiring):
    repo = FakeRepo()
    ask(wiring, repo, agent_result(sources=[source("http://x", source_type="oer")]))
    assert not hasattr(repo, "asked_references")


PRACTICE_SOAL = {
    "question_text": "Berapa keliling persegi bersisi 5?", "options": {"A": "20", "B": "25", "C": "10", "D": "15"}, "correct_option": "A",
    "langkah": ["Empat kali lima."], "kesimpulan": "Dua puluh.", "markup": None, "stimulus": None, "bloom_level": 2,
}


def practice_request(topic="keliling", level=3):
    return {"status": "practice_requested", "practice": {"topic": topic, "level": level}, "message": "", "sources": [], "tool_calls": [], "scope": {"klass": "inti"}}


@pytest.fixture
def practice(monkeypatch, wiring):
    state = SimpleNamespace(source={"text": "materi", "headings": ["Keliling"]}, generated={"soal": PRACTICE_SOAL, "issues": []}, calls=[], agent_calls=0, wiring=wiring)
    monkeypatch.setattr(services.clarifier_practice, "select_source", lambda topic, executor: state.source)

    def generate(topic, source_text, level):
        state.calls.append((topic, source_text, level))
        return state.generated

    def run(question, history, executor):
        state.agent_calls += 1
        return wiring.seen["result"]

    monkeypatch.setattr(services.quizzer_pipeline, "generate_practice", generate)
    monkeypatch.setattr(services.clarifier_agent, "run", run)
    wiring.seen["result"] = practice_request()
    return state


def say(repo, text):
    return asyncio.run(services.ChatbotService(repo, FakeDb()).ask(1, 1, text))


def has_pending(practice):
    return any(key.startswith("clarifier:practice:") for key in practice.wiring.redis.kv)


def test_permintaan_latihan_dijawab_sebagai_pesan_chat_tanpa_kunci(practice):
    repo = FakeRepo()
    result = say(repo, "Buatkan soal latihan keliling")
    assert result["latihan"] == {"tahap": "soal", "pilihan": ["A", "B", "C", "D"]}
    assert "Pilihan A: 20" in result["message"] and "belum ditinjau guru" in result["message"]
    for secret in ("Langkah", "Kesimpulan", "Jawaban yang benar"):
        assert secret not in result["message"]
    assert practice.calls == [("keliling", "materi", 3)] and has_pending(practice)
    assert [row[0] for row in repo.added] == ["user", "assistant"] and repo.added[1][1] == result["message"]


def test_jawaban_huruf_membuka_kunci_tanpa_memanggil_agen(practice):
    repo = FakeRepo()
    say(repo, "Buatkan soal latihan keliling")
    result = say(repo, "b")
    assert practice.agent_calls == 1
    assert result["latihan"] == {"tahap": "hasil", "benar": False} and result["message"].startswith("Jawabanmu salah. Jawaban yang benar opsi A, yaitu 20.")
    assert "Langkah 1. Empat kali lima." in result["message"] and not has_pending(practice)
    assert repo.added[-2][1] == "b" and repo.added[-1][1] == result["message"]


def test_jawaban_benar_dan_pengulangan_huruf_dilanjutkan_ke_agen(practice):
    repo = FakeRepo()
    say(repo, "Buatkan soal latihan keliling")
    assert say(repo, "A")["latihan"]["benar"] is True
    practice.wiring.seen["result"] = agent_result(message="jawaban biasa")
    assert say(repo, "A")["message"] == "jawaban biasa" and practice.agent_calls == 2


def test_huruf_tanpa_latihan_aktif_ditangani_agen(practice):
    practice.wiring.seen["result"] = agent_result(message="jawaban biasa")
    assert say(FakeRepo(), "B")["message"] == "jawaban biasa" and practice.agent_calls == 1


def test_pertanyaan_biasa_saat_latihan_aktif_tidak_menghapus_latihan(practice):
    repo = FakeRepo()
    say(repo, "Buatkan soal latihan keliling")
    practice.wiring.seen["result"] = agent_result(message="penjelasan")
    assert say(repo, "Apa itu keliling?")["message"] == "penjelasan"
    assert has_pending(practice)
    assert say(repo, "A")["latihan"]["tahap"] == "hasil"


def test_latihan_baru_menggantikan_latihan_lama(practice):
    repo = FakeRepo()
    say(repo, "Buatkan soal latihan keliling")
    say(repo, "Buatkan soal latihan luas")
    assert len([key for key in practice.wiring.redis.kv if key.startswith("clarifier:practice:")]) == 1


def test_latihan_ditolak_bila_tidak_ada_bagian_modul_relevan(practice):
    practice.source = None
    result = say(FakeRepo(), "Buatkan soal latihan keliling")
    assert result["latihan"] == {"tahap": "ditolak"} and practice.calls == [] and not has_pending(practice)


def test_latihan_ditolak_jujur_bila_soal_tidak_lolos_pemeriksaan(practice):
    practice.generated = {"soal": None, "issues": ["Stem ambigu."]}
    result = say(FakeRepo(), "Buatkan soal latihan keliling")
    assert result["latihan"] == {"tahap": "ditolak"} and "belum bisa membuat soal latihan" in result["message"] and not has_pending(practice)


def test_latihan_tanpa_topik_ditolak_tanpa_memakai_kuota(practice):
    practice.wiring.seen["result"] = practice_request(topic="")
    result = say(FakeRepo(), "Buatkan soal latihan")
    assert result["latihan"] == {"tahap": "ditolak"} and practice.calls == [] and not any(key.startswith("clarifier:practice-rate") for key in practice.wiring.redis.kv)


def test_latihan_gagal_mencari_sumber_menjadi_penolakan(practice, monkeypatch):
    def broken(topic, executor):
        raise RuntimeError("embedding mati")

    monkeypatch.setattr(services.clarifier_practice, "select_source", broken)
    assert say(FakeRepo(), "Buatkan soal latihan keliling")["latihan"] == {"tahap": "ditolak"}


def test_latihan_dibatasi_per_siswa(practice, monkeypatch):
    monkeypatch.setattr(services, "PRACTICE_RATE_LIMIT", 2)
    repo = FakeRepo()
    say(repo, "Buatkan soal latihan keliling")
    say(repo, "Buatkan soal latihan keliling")
    with pytest.raises(TooManyRequestException):
        say(repo, "Buatkan soal latihan keliling")
    assert len(practice.calls) == 2


def test_latihan_dan_jawabannya_ditolak_saat_kuis_berlangsung(practice):
    repo = FakeRepo()
    say(repo, "Buatkan soal latihan keliling")
    repo.active = [quiz_row(started_minutes_ago=5)]
    for text in ("Buatkan soal latihan keliling", "A"):
        with pytest.raises(BadRequestException, match="kuis sedang berlangsung"):
            say(repo, text)
    repo.active = []
    assert has_pending(practice) and say(repo, "A")["latihan"]["tahap"] == "hasil"


def test_latihan_sesi_lain_tidak_bisa_dijawab(practice):
    repo = FakeRepo()
    say(repo, "Buatkan soal latihan keliling")
    practice.wiring.seen["result"] = agent_result(message="jawaban biasa")
    other = services.ChatbotService(repo, FakeDb())
    assert asyncio.run(other.ask(2, 1, "A"))["message"] == "jawaban biasa"


def test_blok_sumber_tidak_ikut_tersimpan_di_sitasi_pesan(wiring):
    repo = FakeRepo()
    repo.visual = {7: [visual_block(9, "image", image_file="a.png")]}
    result = ask(wiring, repo, agent_result(sources=[source("7")]))
    assert result["sources"][0]["blok"] and "blok" not in repo.added[1][2]["citations"][0]
