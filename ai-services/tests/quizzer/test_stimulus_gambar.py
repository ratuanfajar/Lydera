import pytest

from common import svg_raster
from quizzer import config
from quizzer.stimulus import gambar, registry

SVG = (
    '<svg viewBox="0 0 200 120"><line x1="20" y1="100" x2="180" y2="100" stroke="black"/>'
    '<rect x="40" y="40" width="30" height="60" fill="gray"/><text x="40" y="115">30</text>'
    '<rect x="100" y="20" width="30" height="80" fill="gray"/><text x="100" y="115">50</text></svg>'
)
SPEC = {"svg": SVG}
DESKRIPSI = "Diagram batang dengan dua batang. Batang pertama bernilai 30 dan batang kedua bernilai 50."


def spec(**changes):
    return {**SPEC, **changes}


def invalid(svg):
    return gambar.validate(spec(svg=svg))


def test_gambar_valid_dan_teks_bacaan_adalah_deskripsi_hasil_deskriptor():
    assert gambar.validate(SPEC) == []
    assert gambar.narrate({**SPEC, "deskripsi": DESKRIPSI}).readable_text == DESKRIPSI


def test_finalize_menulis_ulang_svg_bersih_dengan_namespace_dan_mempertahankan_deskripsi_bila_ada():
    result = gambar.finalize({**SPEC, "deskripsi": "  Dua   batang 30 dan 50. "})
    assert result["svg"].startswith('<svg viewBox="0 0 200 120" xmlns="http://www.w3.org/2000/svg">')
    assert result["deskripsi"] == "Dua batang 30 dan 50."
    assert gambar.validate(result) == []
    assert "deskripsi" not in gambar.finalize(SPEC)


@pytest.mark.parametrize(
    "svg",
    [
        '<svg viewBox="0 0 10 10"><script>alert(1)</script></svg>',
        '<svg viewBox="0 0 10 10"><foreignObject/></svg>',
        '<svg viewBox="0 0 10 10"><image href="http://x/y.png"/></svg>',
        '<svg viewBox="0 0 10 10"><use href="#a"/></svg>',
        '<svg viewBox="0 0 10 10"><rect width="5" height="5" onclick="x()"/></svg>',
        '<svg viewBox="0 0 10 10"><rect width="5" height="5" style="fill:url(http://x)"/></svg>',
        '<svg viewBox="0 0 10 10"><rect width="5" height="5" fill="url(http://x/y)"/></svg>',
        '<svg viewBox="0 0 10 10"><rect width="5" height="5" fill="javascript:alert(1)"/></svg>',
        '<svg viewBox="0 0 10 10"><path d="M0 0 L5 5 <script>"/></svg>',
        '<svg viewBox="0 0 10 10"><rect width="5" height="5" transform="rotate(5);alert(1)"/></svg>',
        '<!DOCTYPE svg [<!ENTITY a "aaaa">]><svg viewBox="0 0 10 10"><text>&a;</text></svg>',
        '<svg viewBox="0 0 10 10"><!-- komentar --><rect width="5" height="5"/></svg>',
        '<?xml version="1.0"?><svg viewBox="0 0 10 10"><rect width="5" height="5"/></svg>',
        '<svg viewBox="0 0 10 10"><rect width="5" height="5"',
        "bukan svg", "", None, 5,
        '<svg><rect width="5" height="5"/></svg>', '<svg viewBox="0 0 0 10"><rect width="5" height="5"/></svg>',
        '<svg viewBox="0 0 10 10"></svg>', '<html viewBox="0 0 10 10"><rect/></html>',
        '<svg viewBox="0 0 10 10">teks liar<rect width="5" height="5"/></svg>',
        '<svg viewBox="0 0 10 10"><g>teks ekor<rect width="5" height="5"/></g></svg>',
        '<svg viewBox="0 0 10 10"><g><rect width="5" height="5"/>teks ekor</g></svg>',
        '<svg viewBox="0 0 10 10"><rect id="a" width="5" height="5"/><rect id="a" width="5" height="5"/></svg>',
        '<svg viewBox="0 0 99999999 99999999"><rect width="5" height="5"/></svg>',
        '<svg viewBox="abc 0 0 10 10"><rect width="5" height="5"/></svg>',
        '<svg viewBox="0 0 10 10"><rect width="1e9" height="5"/></svg>',
        '<svg viewBox="0 0 10 10"><rect width="5" height="5" transform="scale(1e9)"/></svg>',
        '<svg viewBox="0 0 10 10"><rect width="5" height="5" transform="javascript"/></svg>',
        '<svg viewBox="0 0 10 10"><path d="eeee eeee 1e999"/></svg>',
        '<svg viewBox="0 0 10 10"><path d="M0 0 L99999 5"/></svg>',
        '<svg viewBox="0 0 10 10"><line x1="0" y1="0" x2="9" y2="9" stroke="black" stroke-dasharray="0.0001"/></svg>',
        '<svg viewBox="0 0 10 10"><rect width="5" height="5" fill="url (http://x)"/></svg>',
        '<svg viewBox="0 0 10 10"><rect width="5" height="5" fill="u\\72l(http://x)"/></svg>',
        '<svg viewBox="0 0 10 10"><rect width="5" height="5" fill="url(#tidakada)"/></svg>',
        '<svg viewBox="0 0 10 10"><line x1="0" y1="0" x2="9" y2="9" marker-end="url(#tidakada)"/></svg>',
        '<svg viewBox="0 0 10 10"><defs><marker id="m"><path d="M0 0 L2 2" marker-end="url(#m)"/></marker></defs><path d="M0 0 L5 5" marker-end="url(#m)"/></svg>',
        '<svg viewBox="0 0 10 10" xmlns:q="http://x/q"><rect width="5" height="5" q:width="9999999"/></svg>',
        '<svg viewBox="0 0 10 10" xmlns:q="http://x/q"><q:rect width="5" height="5"/></svg>',
        '<svg viewBox="0 0 10 10"><text x="1" y="5" opacity="0">99</text></svg>',
        '<svg viewBox="0 0 10 10"><text x="1" y="5">label&#8238;terbalik</text></svg>',
        '<svg viewBox="0 0 10 10"><text x="1" y="5">' + "x" * 250 + "</text></svg>",
        '<svg viewBox="0 0 10 10"><rect width="5" height="5" text-anchor="aneh"/></svg>',
        '<svg viewBox="0 0 10 10"><rect width="5" height="5" fill-opacity="2"/></svg>',
    ],
)
def test_svg_berbahaya_atau_tidak_valid_ditolak(svg):
    assert invalid(svg)


def test_marker_panah_dengan_referensi_lokal_diizinkan():
    svg = ('<svg viewBox="0 0 100 50"><defs><marker id="m" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">'
           '<path d="M0 0 L6 3 L0 6 z"/></marker></defs><line x1="5" y1="25" x2="90" y2="25" stroke="black" marker-end="url(#m)"/></svg>')
    assert invalid(svg) == []


def test_nilai_atribut_wajar_tetap_lolos():
    svg = ('<svg viewBox="0 0 200 100" preserveAspectRatio="xMidYMid"><g transform="translate(10, 5) scale(1.5)"><rect x="1.5" y="2" width="30px" height="20" '
           'fill="#a1b2c3" stroke="black" stroke-width="2" stroke-dasharray="4 2" opacity="0.8"/><path d="M0 0 L10 10 Z" fill="none" stroke="red"/>'
           '<polygon points="0,0 10,0 5,8" fill="currentColor"/><text x="5" y="9" text-anchor="middle" font-weight="bold" font-size="12">Judul</text></g></svg>')
    assert invalid(svg) == []


def test_teks_di_dalam_text_dan_tspan_dipertahankan_saat_dibersihkan():
    svg = '<svg viewBox="0 0 100 50"><text x="5" y="20">Panjang <tspan>5</tspan> cm</text></svg>'
    assert invalid(svg) == []
    assert '<text x="5" y="20">Panjang <tspan>5</tspan> cm</text>' in gambar.finalize(spec(svg=svg))["svg"]


def test_batas_ukuran_dan_jumlah_elemen_dihitung_di_seluruh_pohon(monkeypatch):
    monkeypatch.setattr(config, "STIMULUS_MAX_SVG_CHARS", 50)
    assert "terlalu panjang" in gambar.validate(SPEC)[0]
    monkeypatch.setattr(config, "STIMULUS_MAX_SVG_CHARS", 30000)
    monkeypatch.setattr(config, "SVG_MAX_ELEMENTS", 5)
    flat = '<svg viewBox="0 0 10 10">' + '<rect width="1" height="1"/>' * 6 + "</svg>"
    assert "terlalu besar" in invalid(flat)[0]


def describe(svg=SVG, context="Perhatikan data."):
    issues = []
    return gambar.describe({"svg": svg}, context, issues), issues


def test_describe_memakai_deskriptor_bersama_dan_menyimpan_svg_bersih(fake_vision):
    result, issues = describe()
    assert result["deskripsi"] == DESKRIPSI and result["svg"].startswith("<svg") and "xmlns" in result["svg"]
    assert issues == []
    assert fake_vision and fake_vision[0][1] == "Perhatikan data."


def test_describe_menandai_angka_label_yang_tidak_ada_di_deskripsi(monkeypatch, fake_vision):
    monkeypatch.setattr(gambar, "_render_and_describe", lambda svg, context, feedback="": "Diagram batang dengan dua batang.")
    _, issues = describe()
    assert "angka di dalam gambar belum ada di deskripsi: 30, 50." in issues


def test_describe_menandai_notasi_mentah_dan_menolak_deskripsi_kosong(monkeypatch, fake_vision):
    monkeypatch.setattr(gambar, "_render_and_describe", lambda svg, context, feedback="": "Kurva 30 dan 50 dengan f^x tidak terbaca.")
    _, issues = describe()
    assert any("tidak terbaca" in issue for issue in issues)
    monkeypatch.setattr(gambar, "_render_and_describe", lambda svg, context, feedback="": "   ")
    with pytest.raises(ValueError, match="kosong"):
        describe()


def test_angka_label_dinormalisasi_dan_bilangan_negatif_wajib_disebut(monkeypatch, fake_vision):
    thousands = '<svg viewBox="0 0 10 10"><text x="1" y="5">1.000</text><text x="1" y="8">2,50</text></svg>'
    monkeypatch.setattr(gambar, "_render_and_describe", lambda svg, context, feedback="": "Dua label: seribu 1000 dan 2,5.")
    assert describe(thousands)[1] == []
    negative = '<svg viewBox="0 0 10 10"><text x="1" y="5">-3</text></svg>'
    monkeypatch.setattr(gambar, "_render_and_describe", lambda svg, context, feedback="": "Satu label bernilai 3.")
    assert "negatif" in describe(negative)[1][0]
    monkeypatch.setattr(gambar, "_render_and_describe", lambda svg, context, feedback="": "Satu label bernilai negatif 3.")
    assert describe(negative)[1] == []


def test_gambar_lewat_registry_deskripsi_buatan_llm_dibuang_dan_diganti_hasil_deskriptor(monkeypatch, fake_vision):
    monkeypatch.setattr(config, "STIMULUS_TYPES", ("*",))
    stimulus = {"jenis": "gambar", "narasi": "Perhatikan diagram berikut.", "spesifikasi": {**SPEC, "deskripsi": "karangan LLM"}}
    assert registry.check(stimulus) == []
    result = registry.derive(stimulus, [])
    assert result["spesifikasi"]["deskripsi"] == DESKRIPSI and result["spesifikasi"]["skema_versi"] == 1
    assert result["readable_text"].startswith("Perhatikan diagram berikut. Diagram batang")
    assert "karangan" not in result["readable_text"]


def test_registry_menolak_kunci_asing_dan_tidak_menawarkan_gambar_bila_rasterizer_tidak_ada(monkeypatch, fake_vision):
    monkeypatch.setattr(config, "STIMULUS_TYPES", ("*",))
    assert "tidak dikenal" in registry.check({"jenis": "gambar", "narasi": "", "spesifikasi": {**SPEC, "tambahan": 1}})[0]
    assert "gambar" in registry.typed_names()
    monkeypatch.setattr(svg_raster, "available", lambda: False)
    assert "gambar" not in registry.typed_names()
    assert "tidak tersedia" in registry.check({"jenis": "gambar", "narasi": "", "spesifikasi": SPEC})[0]


def test_describe_menandai_label_teks_gambar_yang_tidak_disebut(monkeypatch, fake_vision):
    svg = '<svg viewBox="0 0 100 50"><text x="5" y="10">Gambar A</text><text x="5" y="30">x</text><rect x="1" y="1" width="5" height="5"/></svg>'
    monkeypatch.setattr(gambar, "_render_and_describe", lambda svg, context, feedback="": "Grafik dengan sumbu x dan satu persegi.")
    _, issues = describe(svg)
    assert issues == ["label di dalam gambar belum disebut di deskripsi: Gambar A."]
    monkeypatch.setattr(gambar, "_render_and_describe", lambda svg, context, feedback="": "Gambar A berisi sumbu x dan satu persegi.")
    assert describe(svg)[1] == []


POINTS_SVG = '<svg viewBox="0 0 100 50"><text x="5" y="10">(-1, 5)</text><text x="5" y="30">(1, 6)</text></svg>'


def test_label_koordinat_tidak_ditandai_bila_angkanya_disebut(monkeypatch, fake_vision):
    monkeypatch.setattr(gambar, "_render_and_describe", lambda svg, context, feedback="": "Titik minus 1, 5 dan titik 1, 6.")
    assert describe(POINTS_SVG)[1] == []


def test_deskripsi_diulang_dengan_umpan_balik_bila_angka_gambar_terlewat(monkeypatch, fake_vision):
    seen = []

    def vision(svg, context, feedback=""):
        seen.append(feedback)
        return "Titik minus 1, 5 dan titik 1, 6." if feedback else "Titik minus 1, 5."

    monkeypatch.setattr(gambar, "_render_and_describe", vision)
    spec, issues = describe(POINTS_SVG)
    assert issues == [] and spec["deskripsi"] == "Titik minus 1, 5 dan titik 1, 6."
    assert seen[0] == "" and "6" in seen[1]


def test_ulangan_deskripsi_yang_lebih_buruk_tidak_dipakai(monkeypatch, fake_vision):
    def vision(svg, context, feedback=""):
        return "Dua titik." if feedback else "Titik minus 1, 5."

    monkeypatch.setattr(gambar, "_render_and_describe", vision)
    spec, issues = describe(POINTS_SVG)
    assert spec["deskripsi"] == "Titik minus 1, 5." and issues
