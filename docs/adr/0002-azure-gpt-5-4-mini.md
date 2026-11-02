# 0002. Semua fitur AI memakai gpt-5.4-mini di Azure

- Status: diterima
- Tanggal: 2026-09

## Konteks

Anotasi sebelumnya memakai Qwen3.7-flash lewat OpenRouter. Kualitas deskripsi tabel dan gambar menentukan apakah siswa tunanetra mendapat makna yang benar, jadi kualitas lebih penting daripada biaya. Dibandingkan: gpt-5.4, gpt-5.4-nano, Grok, Mistral, dan Qwen.

## Keputusan

- Semua fitur memakai `gpt-5.4-mini` pada resource Azure OpenAI (endpoint `/openai/v1/`); OpenRouter tidak dipakai lagi.
- Anotasi (rumus, tabel, gambar, regenerasi): effort `none`, prompt terstruktur (pengamatan lalu deskripsi), aturan "ikuti gambar, bukan teks konteks".
- Quiz dan chatbot: effort `low`. Effort `none` menurunkan akurasi pada tugas menalar.
- Validator quiz: `grok-4.3`, keluarga model berbeda dari generator.
- Scope gate boleh memakai nano. Embedding: `text-embedding-3-large`, 3072 dimensi.
- Model dan effort dikonfigurasi hanya di berkas config: default bersama di `ai-services/common/config.py`, model per fitur di `ai-services/<fitur>/config.py`.

## Konsekuensi

- Hasil bake-off anotasi: skor juri 4,08 vs 3,68 (Qwen); tafsir yang dikarang 1-6 vs 39-43 dari 78 blok; biaya satu bab penuh sekitar 0,16 USD vs 0,003 USD. Biaya lebih tinggi diterima demi kualitas.
- gpt-5.4, nano, Grok, dan Mistral ditolak untuk anotasi (kualitas atau biaya).
- Filter jailbreak Azure mengembalikan HTTP 400 `content_filter`; dipetakan ke `ContentFilterError`.
- Juri LLM berisik; klaim kualitas harus berasal dari minimal 3 ulangan dan verifikasi ke sumber. Lihat skill `/model-eval`.
- Perubahan model atau prompt anotasi menginvalidasi cache lewat `PROMPT_VERSION`.
