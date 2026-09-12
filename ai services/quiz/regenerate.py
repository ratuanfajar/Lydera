import context
import generate
import segment as segment_module
import validate


def regenerate_cluster(conn, stimulus_id, feedback) -> list[tuple[int, dict, dict]]:
    """Regenerasi satu cluster HOTS (stimulus + semua soal yang berbagi stimulus itu) berdasar feedback guru.

    Catatan penyederhanaan v1: tiap soal di cluster diregenerasi lewat panggilan Generation terpisah
    (masing-masing menghasilkan draft stimulus-nya sendiri) -- teks soal_stimulus final yang dipakai
    adalah hasil dari soal PERTAMA di cluster, bukan hasil gabungan/konsensus semua panggilan. Guru
    tetap approve draft hasilnya sebelum final (lihat CONTRACT.md bagian 2), jadi ketidaksesuaian kecil
    di titik ini tertangkap saat review, tapi ini titik yang bisa diperbaiki lagi kalau perlu presisi lebih.

    Mengembalikan list (soal_id, data_baru, hasil_validasi) untuk tiap soal di cluster.
    """
    stimulus = conn.execute("SELECT * FROM soal_stimulus WHERE id = %s", (stimulus_id,)).fetchone()
    if stimulus is None:
        raise ValueError(f"stimulus_id={stimulus_id} tidak ditemukan")

    cluster = conn.execute("SELECT * FROM soal WHERE stimulus_id = %s ORDER BY id", (stimulus_id,)).fetchall()
    if not cluster:
        raise ValueError(f"tidak ada soal untuk stimulus_id={stimulus_id}")

    chapter_id = stimulus["chapter_id"]
    seg_blocks = conn.execute(
        "SELECT reading_order, block_type, readable_text FROM block "
        "WHERE chapter_id = %s AND reading_order BETWEEN %s AND %s ORDER BY reading_order",
        (chapter_id, stimulus["source_reading_order_start"], stimulus["source_reading_order_end"]),
    ).fetchall()
    seg = segment_module.Segment(
        chapter_id=chapter_id,
        title="",
        reading_order_start=stimulus["source_reading_order_start"],
        reading_order_end=stimulus["source_reading_order_end"],
        text="\n".join(b["readable_text"] for b in seg_blocks),
    )

    all_blocks = conn.execute(
        "SELECT reading_order, block_type, readable_text FROM block WHERE chapter_id = %s ORDER BY reading_order",
        (chapter_id,),
    ).fetchall()
    all_segments = segment_module.build_segments(chapter_id, all_blocks)
    summaries = [context.summarize_segment(s) for s in all_segments]
    chapter_summary = context.summarize_chapter(summaries)

    results = []
    for soal in cluster:
        data = generate.generate_soal(seg, chapter_summary, soal["bloom_level"], feedback=feedback)
        stim_text = (data.get("stimulus") or {}).get("readable_text", "")
        val = validate.validate_soal(seg, data["question_text"], data["options"], data["correct_option"], stim_text)
        results.append((soal["id"], data, val))
    return results
