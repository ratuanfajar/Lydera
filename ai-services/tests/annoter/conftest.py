import pytest

from annoter import annoter_pipeline, resilience
from annoter.annotate import Annotated, WindowResult


class SystemicError(resilience.SYSTEMIC_ERRORS[0]):
    def __init__(self):
        Exception.__init__(self, "jaringan putus")


@pytest.fixture
def window_names():
    return ["p0000-0002", "p0003-0005", "p0006-0008", "p0009-0011"]


@pytest.fixture
def systemic_error():
    return SystemicError


@pytest.fixture
def make_windows(tmp_path):
    def create(names):
        for name in names:
            folder = tmp_path / name
            folder.mkdir()
            (folder / "doc_content_list.json").write_text("[]", encoding="utf-8")
        return tmp_path

    return create


@pytest.fixture
def window_result():
    def build(failed=0, attempted=0):
        return WindowResult([Annotated("text", 0, 0, "isi")], failed, attempted)

    return build


@pytest.fixture
def patch_annotate(monkeypatch):
    def apply(outcomes):
        def annotate_window(path, breaker=None):
            outcome = outcomes[path.parent.name]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        monkeypatch.setattr(annoter_pipeline.annotate, "annotate_window", annotate_window)

    return apply
