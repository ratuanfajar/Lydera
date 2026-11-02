# 0006. Quizzer: rencana dulu baru generate, controller berkode, dan verifikasi justifikasi

- Status: diterima
- Tanggal: 2026-10

## Konteks

Pipeline Quizzer membuat satu soal langsung dari satu segmen. Untuk banyak bab dan banyak soal HOTS dan LOTS ini menumpuk cakupan di segmen depan, tidak mengendalikan keragaman, membatalkan seluruh job bila satu soal gagal, dan hanya memverifikasi kunci. Riset ([research 0004](../research/0004-pipeline-quizzer-plan-then-generate.md)) menunjukkan workflow planner, controller berkode, generator, dan evaluator memperbaiki kualitas MCQ pada model yang sama.

## Keputusan

- Pipeline: segmentasi berukuran terbatas (kode), ekstraksi poin per segmen (LLM, di-cache), pemetaan poin ke slot (LLM mengusulkan, kode memvalidasi), generate per slot, pemeriksaan kode, acak opsi, verifikasi Grok dua langkah yang hanya menandai, perbaikan otomatis satu kali khusus masalah dari pemeriksaan kode, laporan cakupan. Rincian di [spec 0001](../specs/0001-pipeline-quizzer-plan-then-generate.md).
- Controller deterministik: kuota guru per bab dan level Bloom per slot ditegakkan kode. LLM tidak menentukan jumlah maupun level.
- Verifikasi memeriksa jawaban dan justifikasi. Temuannya hanya menandai soal (prioritas tinggi dan catatan); soal tidak diubah otomatis, perubahan menunggu feedback guru, karena juri LLM bisa salah dan regenerasi bisa mengganti soal yang sebenarnya benar. Cek duplikat antar soal tidak dilakukan; guru yang menilai. Bloom hanya bendera lunak, bukan syarat lolos, karena juri LLM tidak andal pada level kognitif.
- Satu slot gagal tidak membatalkan job; hasil sebagian disimpan dan kegagalan dilaporkan.
- Guru tidak melihat kisi-kisi sebelum generate; mereka mendapat laporan cakupan sesudahnya. `source_point` disimpan per soal.
- Cache Quizzer memakai `QUIZ_PROMPT_VERSION` sendiri agar `PROMPT_VERSION` Annoter tidak berubah.
- Batas arsitektur tetap: ai-services menghitung, backend menyimpan; `coverage_report` dan `source_point` ditulis backend.

## Konsekuensi

- Lebih banyak panggilan LLM (sekitar 150 untuk 40 soal) dan pipeline lebih kompleks; biaya dan waktu diukur saat verifikasi.
- Dua kolom baru (`soal.source_point`, `quiz_requests.coverage_report`) dan satu migrasi.
- Riset pendukung bukan matematika; kualitas pemetaan poin ke level pada matematika perlu diukur.
- Alternatif yang ditolak: LLM bebas memilih poin dan level (kuota guru bisa dilanggar); kisi-kisi yang harus disetujui guru (menambah langkah UI tanpa kebutuhan mendesak); Bloom sebagai veto (juri tidak andal).
