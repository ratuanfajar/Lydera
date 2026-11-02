# 0005. Pembacaan rumus untuk siswa tunanetra: aturan per notasi, penutup struktur, dan LLM

- Tanggal: 2026-10-27
- Status: dipromosikan ke ADR 0007
- Keyakinan: sedang

## Pertanyaan

Apakah pembacaan rumus per notasi dengan aturan tegas lebih baik daripada bacaan literal buatan LLM untuk siswa tunanetra, dan apakah LLM cukup andal tanpa pemeriksaan tambahan?

## Konteks Lydera

Annoter dan Quizzer membacakan rumus lewat TalkBack dari teks yang dibuat LLM (`common/formula.py`). Teks itu satu-satunya pembawa makna bagi siswa. Bahasa Indonesia; belum ada mesin aturan Indonesia (Speech Rule Engine tidak mencantumkan Indonesia).

## Temuan

- Siswa dengan gangguan penglihatan menilai ucapan matematika gaya kelas (ClearSpeak) lebih familiar, lebih mudah dipahami, dan memberi keyakinan lebih tinggi daripada MathSpeak dan SimpleSpeak, dan keberhasilan mendekode ekspresinya juga lebih tinggi. Sumber: Frankel dkk., ETS, https://doi.org/10.1002/ets2.12103, diakses 2026-10-27.
- Studi lanjutan mendukung bahasa penutup untuk membatasi cakupan akar dan, kemungkinan, struktur lain (pangkat, nilai mutlak, pecahan); penyebutan tingkat kurung bersarang ("kurung ke-n") didukung; jeda panjang atau suara dipercepat kurang didukung; pada ekspresi panjang siswa menulis ulang dan menginginkan navigasi. Sumber: Frankel & Brownstein, https://doi.org/10.1002/ets2.12119, diakses 2026-10-27.
- Pilot ETS: keberhasilan siswa memakai spoken math sebanding dengan braille atau cetak pada soal aljabar tingkat SMA. Sumber: https://doi.org/10.1002/ets2.12132, diakses 2026-10-27.
- Ambiguitas ucapan berat: skor rata-rata 18,93 dari 20 ekspresi dengan aturan MathSpeak dan 8,07 tanpa aturan (tidak berbeda dari tebakan). Sumber: Isaacson dkk., https://repository.rit.edu/cgi/viewcontent.cgi?article=1015&context=jsesd, diakses 2026-10-27 (dibaca dari kutipan hasil).
- Bacaan rumus buatan LLM: kurung dan pengelompokan adalah sumber selisih terbanyak terhadap referensi (24-38% pasangan token berbeda), dan ada catatan masalah konsistensi dan reproduksibilitas; metrik BLEU tidak mengukur apakah pendengar bisa merekonstruksi rumus. Sumber: Volbach & Schlippe, https://arxiv.org/abs/2610.24917, diakses 2026-10-27.
- Bacaan rumus dari LaTeX buatan LLM lalu disintesis TTS tidak selalu bisa dipahami pendengar dan jauh di bawah bacaan ahli pada sebagian besar kategori. Sumber: https://arxiv.org/html/2506.11086 (Interspeech 2025), diakses 2026-10-27.

## Inferensi

- Aturan per notasi yang konsisten dan penanda akhir struktur adalah pilihan yang didukung riset (bukan selera), tetapi semua bukti berbahasa Inggris dan tingkat aljabar.
- LLM saja tidak menjamin konsistensi; perlu pemeriksa struktur di kode.
- Bacaan literal "buka kurung ... tutup kurung" untuk notasi fungsi tidak sejalan dengan prinsip gaya kelas; "f dari g dari empat" lebih dekat dengan ucapan guru.

## Opsi

| Opsi | Kualitas | Biaya | Risiko | Catatan |
|---|---|---|---|---|
| Prompt lama (bacaan literal) | scope sering hilang | rendah | kurung dan pangkat ambigu | dasar |
| Prompt gaya kelas + contoh + pemeriksa struktur (dipilih) | lebih konsisten | kecil (satu retry bila ada temuan) | cakupan notasi langka | |
| Mesin aturan deterministik (parser LaTeX ke ucapan) | paling konsisten | besar | cakupan LaTeX terbatas | bila kegagalan masih tinggi |

## Rekomendasi

Prompt gaya kelas dengan penutup struktur dan contoh per kategori, ditambah pemeriksa struktur di kode dan satu kali coba ulang; tandai yang masih bermasalah untuk guru. Uji dengar nyata dengan siswa atau guru SLB tetap gerbang sebelum soal berumus dipakai siswa.

## Belum diverifikasi

Keterdengaran sebenarnya di TalkBack berbahasa Indonesia; kualitas pada notasi langka (limit dua sisi, integral lipat, notasi kimia); kesetiaan pada rumus buatan Quizzer selain set uji; apakah aturan tertentu (mis. "kurung kedua") nyaman bagi pendengar Indonesia.

## Tindak lanjut

ADR 0007; evaluasi A/B dan hasilnya tercatat di ADR dan `docs/planning/findings.md` (F-042).
