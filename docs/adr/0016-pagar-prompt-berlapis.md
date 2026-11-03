# 0016. Pagar prompt berlapis terhadap injeksi, kebocoran, dan pertanyaan di luar konteks

- Status: diterima
- Tanggal: 2026-11-03

## Konteks

Masukan tak tepercaya masuk ke prompt dari banyak arah: pertanyaan dan langkah siswa, teks modul dan OCR hasil PDF guru, takarir dan teks di dalam gambar, umpan balik guru, dan hasil pencarian web. Sebelumnya hanya Clarifier yang menyatakan hasil tool sebagai data, tanpa pembatas, tanpa penyaring masukan, dan tanpa pemeriksa kebocoran instruksi di keluaran.

## Keputusan

Pertahanan berlapis di `ai-services/common/guardrails.py`; tidak ada yang bergantung pada satu lapis:

- Aturan anti-injeksi ditambahkan otomatis ke RULES semua prompt sistem oleh `build_prompt`, dan disisipkan oleh `llm` dan `chat_with_tools` bila prompt dibuat tanpa `build_prompt`.
- `build_input` membungkus bagian data dalam tag dan menetralkan tag penutup buatan; simbol matematika `<` dan `>` tidak diubah.
- Penyaring pola tanpa LLM (`injection_markers`, teks dinormalkan): pertanyaan siswa peniru instruksi ditolak sebelum pencarian dan model; hasil web dan potongan modul yang meniru instruksi dibuang; langkah siswa, sumber soal, dan blok anotasi yang memuatnya ditandai untuk ditinjau. Ajakan berperan hanya ditandai pada masukan siswa.
- Pemeriksa keluaran (`leaks_instructions`) membuang jawaban atau keterangan yang memuat isi instruksi.
- Clarifier menolak permintaan di luar belajar matematika (kode, esai, tugas lain, konten berbahaya, menyuruh berpura-pura) dan mengarahkan siswa yang tertekan ke guru atau orang dewasa tepercaya.
- Prompt tidak boleh menyebut nama dokumen proyek; dijaga tes.

## Konsekuensi

- Versi prompt dinaikkan, sehingga cache anotasi lama tidak dipakai.
- Penyaring pola tidak menangkap semua parafrasa dan bahasa; teks di dalam gambar hanya dijaga aturan prompt; belum ada batas laju untuk pesan chat biasa.
- Efektivitas terhadap model nyata belum diukur; perlu set uji serangan dengan tiga ulangan sebelum diklaim.
