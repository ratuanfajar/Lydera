from quizzer import config, segment


def block(order, text, kind="text"):
    return {"reading_order": order, "block_type": kind, "readable_text": text}


def long_blocks(count, size=500):
    return [block(i * 10, f"blok {i} " + "x" * size) for i in range(count)]


def test_bab_kosong_tidak_menghasilkan_segmen():
    assert segment.build_segments(1, []) == []
    assert segment.build_segments(1, [block(10, "   ")]) == []


def test_bab_pendek_menjadi_satu_segmen_dengan_batas_dan_judul():
    blocks = [block(10, "Judul", "heading"), block(20, "isi satu"), block(30, "isi dua")]
    [seg] = segment.build_segments(7, blocks)
    assert (seg.chapter_id, seg.title, seg.reading_order_start, seg.reading_order_end) == (7, "Judul", 10, 30)
    assert seg.labeled_text == "[10] Judul\n[20] isi satu\n[30] isi dua"
    assert seg.context_text == ""


def test_segmen_tanpa_heading_diberi_judul_bagian():
    [seg] = segment.build_segments(1, [block(10, "isi")])
    assert seg.title == "Bagian 1"


def test_materi_pembuka_dibuang_sampai_heading_berikutnya():
    blocks = [
        block(10, "Tujuan Pembelajaran", "heading"), block(20, "Siswa mampu ..."),
        block(30, "Konsep Utama", "heading"), block(40, "isi konsep"),
    ]
    [seg] = segment.build_segments(1, blocks)
    assert [b["reading_order"] for b in seg.blocks] == [30, 40]


def test_bab_panjang_dipotong_berurutan_tanpa_blok_hilang_atau_ganda():
    blocks = long_blocks(60)
    segments = segment.build_segments(1, blocks)
    assert len(segments) > 1
    covered = [b["reading_order"] for s in segments for b in s.blocks]
    assert covered == [b["reading_order"] for b in blocks]


def test_segmen_kedua_membawa_konteks_dari_blok_sebelumnya():
    segments = segment.build_segments(1, long_blocks(60))
    previous = segments[0].blocks[-config.OVERLAP_BLOCKS:]
    assert segments[1].context_text == "\n".join(b["readable_text"] for b in previous)


def test_ekor_terlalu_pendek_digabung_ke_segmen_terakhir():
    blocks = long_blocks(8) + [block(900, "ekor pendek")]
    segments = segment.build_segments(1, blocks)
    assert segments[-1].blocks[-1]["reading_order"] == 900
    assert len(segments[-1].text) >= config.SEGMENT_MIN_TAIL_CHARS


def test_rumus_dan_tabel_tidak_dipisah_dari_blok_sebelumnya():
    blocks = long_blocks(7, 560) + [block(900, "persamaan", "formula"), block(910, "lanjutan")]
    for seg in segment.build_segments(1, blocks):
        assert seg.blocks[0]["block_type"] != "formula"


def test_span_text_menambah_margin_blok_di_kedua_sisi():
    rows = [block(i * 10, f"b{i}") for i in range(20)]
    text = segment.span_text(rows, 100, 100)
    assert text.split("\n") == [f"b{i}" for i in range(7, 14)]


def test_span_text_tanpa_blok_pada_rentang_kosong():
    assert segment.span_text([block(10, "a")], 500, 600) == ""


def test_span_text_mengurangi_margin_bila_melebihi_batas_karakter(monkeypatch):
    monkeypatch.setattr(config, "SOURCE_MAX_CHARS", 30)
    rows = [block(i * 10, "x" * 10) for i in range(20)]
    text = segment.span_text(rows, 100, 100)
    assert "x" * 10 in text and len(text) <= 30


def visual_blocks():
    types = ["text", "text", "image", "text", "text", "text", "text", "text", "table", "text"]
    return [{"reading_order": i * 10, "block_type": t, "readable_text": f"blok {i}"} for i, t in enumerate(types)]


def test_visual_kinds_mencakup_gambar_dan_tabel_pada_jendela_sumber():
    blocks = visual_blocks()
    assert segment.visual_kinds(blocks, 10, 10) == ("image",)
    assert segment.visual_kinds(blocks, 80, 80) == ("table",)
    assert segment.visual_kinds(blocks, 0, 0) == ("image",)


def test_visual_kinds_kosong_bila_jendela_tanpa_gambar_atau_tabel_dan_untuk_rentang_tidak_ada():
    blocks = [{"reading_order": i * 10, "block_type": "text", "readable_text": f"blok {i}"} for i in range(12)]
    assert segment.visual_kinds(blocks, 50, 60) == ()
    assert segment.visual_kinds(blocks, 9999, 9999) == ()
