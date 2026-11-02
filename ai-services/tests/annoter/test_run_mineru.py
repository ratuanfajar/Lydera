import asyncio

import pytest

from annoter import run_mineru


@pytest.mark.parametrize(
    "line, expected",
    [
        ("Layout Predict: 40%|####", (15, "Layout Predict: 40%")),
        ("Layout Predict: 100%", (30, "Layout Predict: 100%")),
        ("MFR Predict: 50%|##", (40, "Formula Recognition: 50%")),
        ("Processing pages: 10%", (52, "Extracting Pages: 10%")),
        ("OCR-det 100%|####", (70, "Extracting Pages: 100%")),
        ("Layout Predict: tanpa persen", None),
        ("baris lain 50%", None),
        ("", None),
    ],
)
def test_stage_progress_memetakan_tahap_ke_persen_keseluruhan(line, expected):
    assert run_mineru.stage_progress(line) == expected


def test_build_command_meneruskan_start_dan_end(tmp_path):
    command = run_mineru.build_command(
        tmp_path / "a.pdf", tmp_path, backend="pipeline", method="auto", lang=None, start=3, end=5, no_formula=False, no_table=False,
    )
    assert command[command.index("-s") + 1] == "3"
    assert command[command.index("-e") + 1] == "5"


def test_prepare_membuat_folder_dan_mengembalikan_path_absolut(tmp_path):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF")
    resolved_pdf, resolved_out = run_mineru._prepare(pdf, tmp_path / "keluar" / "baru")
    assert resolved_pdf == pdf.resolve() and resolved_out.is_dir()


def test_prepare_pdf_tidak_ada_mengembalikan_none(tmp_path, capsys):
    assert run_mineru._prepare(tmp_path / "tidak-ada.pdf", tmp_path) is None
    assert "PDF tidak ditemukan" in capsys.readouterr().err


def test_environment_memuat_device_dan_vram_bila_ada():
    assert run_mineru._environment("cpu", None) == {"MINERU_DEVICE_MODE": "cpu"}
    assert run_mineru._environment("cpu", 4096) == {"MINERU_DEVICE_MODE": "cpu", "MINERU_VIRTUAL_VRAM_SIZE": "4096"}


def test_environment_cuda_tanpa_gpu_memberi_peringatan(monkeypatch, capsys):
    monkeypatch.setattr(run_mineru, "torch_sees_gpu", lambda: False)
    assert run_mineru._environment("cuda", None)["MINERU_DEVICE_MODE"] == "cuda"
    assert "CUDA diminta" in capsys.readouterr().err


def test_finish_menghapus_file_debug_kecuali_diminta_disimpan(tmp_path):
    for name in ("a_middle.json", "a_content_list.json"):
        (tmp_path / name).write_text("[]", encoding="utf-8")
    run_mineru._finish(tmp_path, "a", keep_debug=True)
    assert (tmp_path / "a_middle.json").exists()
    run_mineru._finish(tmp_path, "a", keep_debug=False)
    assert not (tmp_path / "a_middle.json").exists() and (tmp_path / "a_content_list.json").exists()


class FakeStderr:
    def __init__(self, lines):
        self.lines = iter(lines)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.lines)
        except StopIteration:
            raise StopAsyncIteration


class FakeProcess:
    def __init__(self, lines, code=0):
        self.stderr, self.returncode = FakeStderr(lines), code

    async def wait(self):
        return self.returncode


@pytest.fixture
def mineru_process(monkeypatch, tmp_path):
    seen = {}

    def launch(lines, code=0):
        async def spawn(*args, **kwargs):
            seen.update(kwargs)
            return FakeProcess(lines, code)

        monkeypatch.setattr(run_mineru.asyncio, "create_subprocess_exec", spawn)
        return seen

    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF")
    return launch, pdf


def test_run_async_meneruskan_progress_ke_callback_dan_tidak_memakai_stdout_pipe(mineru_process, tmp_path):
    launch, pdf = mineru_process
    seen = launch([b"Layout Predict: 40%\n", b"\n", b"noise\n", b"MFR Predict: 100%\n"])
    updates = []

    async def callback(percent, message):
        updates.append((percent, message))

    assert asyncio.run(run_mineru.run_async(pdf, tmp_path / "out", device="cpu", progress_callback=callback)) == 0
    assert updates == [(15, "Layout Predict: 40%"), (50, "Formula Recognition: 100%")]
    assert seen["stdout"] == asyncio.subprocess.DEVNULL


def test_run_async_kode_keluar_bukan_nol_dikembalikan(mineru_process, tmp_path):
    launch, pdf = mineru_process
    launch([], code=3)
    assert asyncio.run(run_mineru.run_async(pdf, tmp_path / "out", device="cpu")) == 3


def test_run_async_meneruskan_start_dan_end_ke_build_command(mineru_process, tmp_path, monkeypatch):
    launch, pdf = mineru_process
    launch([])
    seen = {}

    def build(pdf_path, out, **kwargs):
        seen.update(kwargs)
        return ["mineru"]

    monkeypatch.setattr(run_mineru, "build_command", build)
    asyncio.run(run_mineru.run_async(pdf, tmp_path / "out", start=3, end=5, device="cpu"))
    assert (seen["start"], seen["end"]) == (3, 5)


def test_run_async_modul_mineru_tidak_ditemukan_mengembalikan_127(tmp_path, monkeypatch):
    async def spawn(*args, **kwargs):
        raise FileNotFoundError

    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(run_mineru.asyncio, "create_subprocess_exec", spawn)
    assert asyncio.run(run_mineru.run_async(pdf, tmp_path / "out", device="cpu")) == 127


def test_run_async_pdf_tidak_ada_mengembalikan_2(tmp_path):
    assert asyncio.run(run_mineru.run_async(tmp_path / "tidak-ada.pdf", tmp_path / "out", device="cpu")) == 2
