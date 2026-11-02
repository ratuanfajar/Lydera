# 0004. Pipeline Quizzer: rencana dulu baru generate, dan verifikasi justifikasi

- Tanggal: 2026-10-27
- Status: dipromosikan ke spec 0001 dan ADR 0006
- Keyakinan: sedang

## Pertanyaan

Apakah alur Quizzer yang membuat satu soal langsung dari satu segmen layak untuk banyak bab dan banyak soal HOTS/LOTS, dan apakah alur "ekstrak poin, petakan ke CP dan Bloom, generate, verifikasi" lebih baik?

## Konteks Lydera

Guru memilih beberapa bab, tiap bab punya CP dan jumlah HOTS/LOTS sendiri. Soal dibacakan pembaca layar, jadi stimulus hanya teks. ai-services komputasi murni; backend menulis DB. Model generator `gpt-5.4-mini`, validator `grok-4.3`.

## Temuan

- ReQUESTA memecah pembuatan MCQ menjadi preprocessor (aturan), planner (LLM: ringkas segmen, tentukan konsep dan inferensi, susun rencana soal), controller (kode: menugaskan segmen dan konsep ke generator), generator per jenis, evaluator (checklist: kejernihan stem, keselarasan stem dan kunci, kewajaran distraktor; yang gagal dikembalikan ke generator dengan saran revisi), formatter (kode: mengacak opsi, melabeli). Dengan model GPT-5 yang sama, 200 soal dari 20 bacaan: item ReQUESTA lebih sulit dan lebih diskriminatif, lebih relevan topik, distraktor lebih baik; kejernihan tulisan soal inferensial dan gagasan utama lebih rendah. Ada modul pemendek opsi karena panjang opsi tidak seimbang adalah kegagalan umum. Sumber: arXiv 2602.03704 (Tian dkk., Feb 2026), diakses 2026-10-27. Batas: bacaan akademik sekitar 400 kata dari OpenStax, bukan matematika.
- Bias posisi kunci saat generate terstruktur dan per keluarga model: pada 10 LLM, opsi D hampir selalu kurang terwakili; instruksi "seimbangkan" membantu model reasoning tetapi model kecil tetap sulit. Sumber: arXiv 2605.01846 (Tang dkk., Mei 2026), diakses 2026-10-27.
- Soal berlevel Bloom sesuai yang diminta hanya sebagian: 78% soal berkualitas tinggi, dan dari itu 65,56% sesuai level menurut dua rater manusia; juri LLM berbeda signifikan dari ahli dan cenderung melabeli soal sebagai Apply atau Analyze. Sumber: arXiv 2408.04394, diakses 2026-10-27 (dari ringkasan hasil pencarian, bukan dibaca penuh).
- Data sendiri: bab sampel 52-62 ribu karakter (413-439 blok); segmen `A.` saat ini 14-22 ribu karakter dan hanya 3 per bab; Bloom exact-match sekitar 0,75 (3 ulangan, dua juri); kunci terpanjang sama dengan kunci benar pada 11 dari 24 soal setelah perbaikan prompt; validator menangkap 2 dari 2 soal bermasalah tetapi tidak memeriksa langkah dan kesimpulan.

## Inferensi

- Pola planner lalu controller berkode lalu generator lalu evaluator cocok dengan strategi guru; ide kunci adalah controller deterministik yang menegakkan kuota guru.
- Level Bloom sebaiknya ditentukan kode dari kuota, bukan dipilih LLM, karena LLM tidak andal menilai level.
- Bloom jangan jadi veto verifikasi; cukup bendera lunak.
- Satu poin ringkasan tanpa teks sumber berisiko salah rumus; tiap poin perlu rujukan sumber.

## Opsi

| Opsi | Kualitas | Biaya | Risiko | Catatan |
|---|---|---|---|---|
| Alur sekarang (satu soal per segmen) | cukup untuk satu bab | rendah | cakupan menumpuk di segmen depan, tanpa kontrol keragaman, satu kegagalan membatalkan job | |
| Plan-then-generate dengan controller berkode | lebih tinggi (ReQUESTA) | sekitar 150 panggilan untuk 40 soal | kompleksitas pipeline | dipilih |
| LLM memilih poin dan level tanpa batasan kode | tidak terkendali | sama | kuota guru bisa dilanggar | ditolak |

## Rekomendasi

Plan-then-generate dengan controller berkode, verifier Grok dua langkah (jawab buta, lalu audit justifikasi), satu kali perbaikan otomatis, isolasi kegagalan per slot, dan pasca-proses deterministik.

## Belum diverifikasi

Apakah satu bab utuh dalam satu panggilan sama baiknya dengan ekstraksi per segmen untuk `gpt-5.4-mini`; waktu total dan biaya untuk puluhan soal; kualitas pemetaan poin ke level pada matematika (riset di atas bukan matematika).

## Tindak lanjut

Spec `docs/specs/0001-pipeline-quizzer-plan-then-generate.md`; ADR `docs/adr/0006-quizzer-plan-then-generate.md`.
