import pytest

from common import svg_raster
from quizzer.stimulus import gambar

DESCRIPTION = "Diagram batang dengan dua batang. Batang pertama bernilai 30 dan batang kedua bernilai 50."


@pytest.fixture
def fake_vision(monkeypatch):
    calls = []
    monkeypatch.setattr(svg_raster, "available", lambda: True)
    monkeypatch.setattr(gambar, "_render_and_describe", lambda svg, context, feedback="": calls.append((svg, context)) or DESCRIPTION)
    return calls
