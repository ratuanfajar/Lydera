import threading
from pathlib import Path

FONT_DIR = Path(__file__).parent / "fonts"
FONT_FAMILY = "Liberation Sans"
DEFAULT_WIDTH = 800
BACKGROUND = "white"
_LOCK = threading.Lock()


class RenderError(ValueError):
    pass


def available() -> bool:
    try:
        import resvg_py  # noqa: F401
    except ImportError:
        return False
    return True


def render_png(svg: str, directory: Path, width: int = DEFAULT_WIDTH) -> Path:
    """Rasterisasi SVG yang sudah dibersihkan menjadi PNG berlatar putih; font memakai berkas di common/fonts bila ada."""
    import resvg_py

    fonts = sorted(FONT_DIR.glob("*.ttf"))
    options = {"skip_system_fonts": True, "font_files": [str(font) for font in fonts], "font_family": FONT_FAMILY, "sans_serif_family": FONT_FAMILY} if fonts else {}
    try:
        with _LOCK:
            png = resvg_py.svg_to_bytes(svg_string=svg, background=BACKGROUND, width=width, **options)
    except Exception as exc:
        raise RenderError(str(exc)[:200] or "SVG tidak dapat dirender") from exc
    path = directory / "stimulus.png"
    path.write_bytes(bytes(png))
    return path
