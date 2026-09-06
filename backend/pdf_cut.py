from pathlib import Path

from pypdf import PdfReader, PdfWriter


def cut(source_pdf, out_pdf, start_page: int, end_page: int) -> Path:
    """Potong PDF ke rentang halaman [start_page, end_page], 0-based inklusif."""
    reader = PdfReader(str(source_pdf))
    last = len(reader.pages) - 1
    if start_page < 0 or end_page > last or end_page < start_page:
        raise ValueError(f"rentang halaman {start_page}-{end_page} di luar jangkauan (0-{last})")

    writer = PdfWriter()
    for i in range(start_page, end_page + 1):
        writer.add_page(reader.pages[i])

    out_pdf = Path(out_pdf)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    with open(out_pdf, "wb") as f:
        writer.write(f)
    return out_pdf
