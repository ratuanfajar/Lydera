import pytest

from annoter import image, priority, prompts


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Parabola dengan titik puncak di tiga koma dua.", "normal"),
        ("Label sumbu tidak terbaca.", "high"),
        ("Angka pada panel tidak dapat dibaca.", "high"),
        ("Kesejajaran garis tidak dapat dipastikan.", "normal"),
    ],
)
def test_image_priority_menandai_teks_tidak_terbaca_saja(text, expected):
    assert priority.image_priority(image.ImageAnnotation("geometri", text)) == expected


def test_image_priority_dekoratif_tetap_normal():
    assert priority.image_priority(image.ImageAnnotation(image.DECORATIVE, "tidak terbaca")) == "normal"


def test_aturan_bukti_visual_masuk_ke_semua_prompt_gambar():
    rule = prompts.VISUAL_EVIDENCE_RULES[0]
    assert rule in prompts.image_system()
    assert all(rule in prompts.image_kind_system(kind) for kind in prompts.KIND_RULES)


def test_pembuka_pada_gambar_dilarang():
    assert "Pada gambar" in prompts.NO_OPENER_RULE


def test_aturan_gaya_deskripsi_masuk_ke_semua_prompt_gambar():
    rule = prompts.DESCRIPTION_STYLE_RULES[1]
    assert rule in prompts.image_system()
    assert all(rule in prompts.image_kind_system(kind) for kind in prompts.KIND_RULES)
