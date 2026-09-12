import context
import generate
import segment as segment_module
import validate


def compute_cluster(chapter_id, all_blocks, reading_order_start, reading_order_end,
                     soal_bloom_levels, feedback) -> list[tuple[int, dict, dict]]:
    """Hitung ulang (generate + validate) satu cluster HOTS, tanpa menyentuh DB -- pemanggil yang
    menyimpan hasilnya (lihat `regenerate_cluster` untuk versi psycopg, atau
    `backend/app/tasks/quiz_tasks.py` untuk versi async SQLAlchemy).

    Catatan penyederhanaan v1: tiap soal di cluster diregenerasi lewat panggilan Generation terpisah
    (masing-masing menghasilkan draft stimulus-nya sendiri) -- teks soal_stimulus final yang dipakai
    adalah hasil dari soal PERTAMA di cluster, bukan hasil gabungan/konsensus semua panggilan. Guru
    tetap approve draft hasilnya sebelum final (lihat CONTRACT.md bagian 2), jadi ketidaksesuaian kecil
    di titik ini tertangkap saat review, tapi ini titik yang bisa diperbaiki lagi kalau perlu presisi lebih.

    `all_blocks`: seluruh block bab ini (reading_order, block_type, readable_text), dipakai untuk
    membangun ulang segmen sumber dan ringkasan bab. `reading_order_start`/`reading_order_end`:
    rentang blok sumber stimulus cluster ini. `soal_bloom_levels`: list (soal_id, bloom_level) untuk
    tiap soal di cluster. Mengembalikan list (soal_id, data_baru, hasil_validasi).
    """
    seg_blocks = [b for b in all_blocks if reading_order_start <= b["reading_order"] <= reading_order_end]
    seg = segment_module.Segment(
        chapter_id=chapter_id,
        title="",
        reading_order_start=reading_order_start,
        reading_order_end=reading_order_end,
        text="\n".join(b["readable_text"] for b in seg_blocks),
    )

    all_segments = segment_module.build_segments(chapter_id, all_blocks)
    summaries = [context.summarize_segment(s) for s in all_segments]
    chapter_summary = context.summarize_chapter(summaries)

    results = []
    for soal_id, bloom_level in soal_bloom_levels:
        data = generate.generate_soal(seg, chapter_summary, bloom_level, feedback=feedback)
        stim_text = (data.get("stimulus") or {}).get("readable_text", "")
        val = validate.validate_soal(seg, data["question_text"], data["options"], data["correct_option"], stim_text)
        results.append((soal_id, data, val))
    return results


def regenerate_cluster(conn, stimulus_id, feedback) -> list[tuple[int, dict, dict]]:
    """Versi psycopg (CLI/testing manual): baca stimulus + cluster dari DB, lalu panggil `compute_cluster`."""
    stimulus = conn.execute("SELECT * FROM soal_stimulus WHERE id = %s", (stimulus_id,)).fetchone()
    if stimulus is None:
        raise ValueError(f"stimulus_id={stimulus_id} tidak ditemukan")

    cluster = conn.execute("SELECT * FROM soal WHERE stimulus_id = %s ORDER BY id", (stimulus_id,)).fetchall()
    if not cluster:
        raise ValueError(f"tidak ada soal untuk stimulus_id={stimulus_id}")

    chapter_id = stimulus["chapter_id"]
    all_blocks = conn.execute(
        "SELECT reading_order, block_type, readable_text FROM block WHERE chapter_id = %s ORDER BY reading_order",
        (chapter_id,),
    ).fetchall()
    soal_bloom_levels = [(soal["id"], soal["bloom_level"]) for soal in cluster]
    return compute_cluster(
        chapter_id, all_blocks,
        stimulus["source_reading_order_start"], stimulus["source_reading_order_end"],
        soal_bloom_levels, feedback,
    )
