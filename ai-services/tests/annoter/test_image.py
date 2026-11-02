import pytest

from annoter import image
from annoter.preprocess import Block, Route


@pytest.fixture
def store(monkeypatch):
    memory = {}
    monkeypatch.setattr(image.cache, "get", lambda namespace, *parts: memory.get((namespace, parts)))
    monkeypatch.setattr(image.cache, "put", lambda namespace, value, *parts: memory.__setitem__((namespace, parts), value))
    return memory


@pytest.fixture
def block(tmp_path):
    path = tmp_path / "abc.jpg"
    path.write_bytes(b"x")
    return Block(Route.IMAGE, 0, 0, caption="Gambar 1", image_path=path)


def fake_llm(monkeypatch, kinds, description="Kurva naik dari kiri bawah ke kanan atas."):
    calls = {"json": [], "text": []}
    answers = iter(kinds)

    def vision_json(system, user, path, **kwargs):
        calls["json"].append(system)
        return next(answers)

    def vision(system, user, path, **kwargs):
        calls["text"].append(system)
        return description

    monkeypatch.setattr(image.llm, "complete_vision_json", vision_json)
    monkeypatch.setattr(image.llm, "complete_vision", vision)
    return calls


@pytest.mark.parametrize(
    "final, expected",
    [
        ({"jenis": "grafik", "yakin": 5}, ("grafik", False)),
        ({"jenis": "grafik", "yakin": 4}, ("grafik", False)),
        ({"jenis": "grafik", "yakin": 3}, ("grafik", True)),
        ({"jenis": "dekoratif", "yakin": 4}, ("dekoratif", False)),
        ({"jenis": "dekoratif", "yakin": 2}, ("ilustrasi_konteks", True)),
        ({"jenis": "aneh", "yakin": 5}, ("aneh", True)),
        ({"jenis": "diagram", "yakin": "bukan angka"}, ("diagram", True)),
        ({"jenis": "diagram"}, ("diagram", True)),
    ],
)
def test_resolve_final_menetapkan_jenis_dan_ketidakpastian(final, expected):
    assert image.resolve_final(final) == expected


def test_gambar_tidak_ada_berhasil_kosong(tmp_path):
    missing = Block(Route.IMAGE, 0, 0, image_path=tmp_path / "tidak-ada.jpg")
    assert image.annotate_image(missing) == image.ImageAnnotation("", "")
    assert image.annotate_image(Block(Route.IMAGE, 0, 0)) == image.ImageAnnotation("", "")


def test_gambar_dekoratif_yakin_dilewati_tanpa_deskripsi(block, store, monkeypatch):
    calls = fake_llm(monkeypatch, [{"jenis": "dekoratif", "yakin": 5}] * 3)
    assert image.annotate_image(block) == image.ImageAnnotation("dekoratif", "")
    assert calls["text"] == []


def test_gambar_yakin_memakai_prompt_jenis_dan_dibersihkan_speakable(block, store, monkeypatch):
    calls = fake_llm(monkeypatch, [{"jenis": "grafik", "yakin": 5}] * 3, description='Laju (m/s) pada "grafik".')
    result = image.annotate_image(block)
    assert (result.kind, result.uncertain, result.text) == ("grafik", False, "Laju (meter per sekon) pada grafik.")
    assert image.prompts.KIND_RULES["grafik"][0] in calls["text"][0]


def test_gambar_ragu_memakai_prompt_umum_dan_ditandai(block, store, monkeypatch):
    calls = fake_llm(monkeypatch, [{"jenis": "grafik", "yakin": 2}] * 3)
    result = image.annotate_image(block)
    assert (result.kind, result.uncertain) == ("grafik", True)
    assert image.prompts.KIND_RULES["grafik"][0] not in calls["text"][0]


def test_jenis_tidak_dikenal_disimpan_kosong_dan_ditandai(block, store, monkeypatch):
    fake_llm(monkeypatch, [{"jenis": "aneh", "yakin": 5}] * 3)
    result = image.annotate_image(block)
    assert (result.kind, result.uncertain) == ("", True)


def test_klasifikasi_dan_deskripsi_dipakai_dari_cache_pada_panggilan_kedua(block, store, monkeypatch):
    calls = fake_llm(monkeypatch, [{"jenis": "grafik", "yakin": 5}] * 3)
    image.annotate_image(block, "teks sekitar")
    first = (len(calls["json"]), len(calls["text"]))
    image.annotate_image(block, "teks sekitar")
    assert (len(calls["json"]), len(calls["text"])) == first == (3, 1)


def test_konteks_dipotong_untuk_klasifikasi_percobaan_kedua(block, store, monkeypatch):
    fake_llm(monkeypatch, [{"jenis": "grafik", "yakin": 5}] * 3)
    seen = []
    original = image.prompts.image_classifier_input
    monkeypatch.setattr(image.prompts, "image_classifier_input", lambda caption, context="": seen.append(context) or original(caption, context))
    image.classify_image(block, "x" * 1000)
    assert seen == ["", "x" * image.annoter_config.CLASSIFY_CONTEXT_CHARS]
