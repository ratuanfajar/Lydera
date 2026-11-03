import pytest

from common import svg_raster

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><rect x="5" y="5" width="40" height="20" fill="gray"/><text x="5" y="40" font-size="10">30</text></svg>'
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@pytest.mark.skipif(not svg_raster.available(), reason="resvg-py belum terpasang")
def test_render_png_menghasilkan_berkas_png_berlatar_putih(tmp_path):
    path = svg_raster.render_png(SVG, tmp_path, width=200)
    data = path.read_bytes()
    assert path.parent == tmp_path and data.startswith(PNG_SIGNATURE) and len(data) > 100


def test_available_false_bila_resvg_tidak_dapat_diimpor(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def refuse(name, *args, **kwargs):
        if name == "resvg_py":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", refuse)
    assert svg_raster.available() is False


@pytest.mark.skipif(not svg_raster.available(), reason="resvg-py belum terpasang")
def test_svg_yang_tidak_dapat_diurai_menjadi_render_error(tmp_path):
    with pytest.raises(svg_raster.RenderError):
        svg_raster.render_png("bukan svg sama sekali", tmp_path)
