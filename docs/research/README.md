# Catatan riset

Hasil riset dan brainstorming yang layak diingat. Satu berkas per topik: `NNNN-slug.md` (4 digit, nomor berikutnya dari yang tertinggi). Gunakan [_template.md](_template.md).

Aturan:
- Tiap temuan menyebut sumber dan tanggal akses. Tanpa sumber, tandai sebagai inferensi.
- Pisahkan fakta (dari sumber) dan inferensi (penilaian sendiri).
- Klaim kualitas model tidak boleh bersandar pada satu sumber atau satu kali jalan; lihat skill `model-eval`.
- Nyatakan tingkat keyakinan dan apa yang belum diverifikasi.
- Catatan yang berujung keputusan dipromosikan menjadi ADR di [../adr/](../adr/) atau spec di [../specs/](../specs/), dan catatan menautkannya.
- Catatan tidak diedit untuk mengubah kesimpulan lama; tambahkan bagian "Pembaruan" bertanggal.

Indeks:

| No | Topik | Status |
|---|---|---|
| [0001](0001-filter-sumber-web-clarifier.md) | Filter sumber web Clarifier: allowlist domain atau pola wildcard | selesai (input untuk Fase 6; rekomendasi final di Pembaruan 3) |
| [0002](0002-ab-prompt-annoter.md) | A/B prompt Annoter: format seragam, rumus few-shot, masukan gambar | selesai (dipakai di `ai-services/annoter/prompts.py`, `PROMPT_VERSION` 9) |
| [0003](0003-klasifikasi-gambar-annoter.md) | Klasifikasi gambar Annoter: apakah prompt per jenis lebih baik | selesai. Rekomendasi saya: penyaring dekoratif + prompt umum. Keputusan user (2026-10-27): prompt per jenis (varian C) tetap diterapkan untuk produksi. |
| [0004](0004-pipeline-quizzer-plan-then-generate.md) | Pipeline Quizzer: rencana dulu baru generate, dan verifikasi justifikasi | dipromosikan ke spec 0001 dan ADR 0006 |
