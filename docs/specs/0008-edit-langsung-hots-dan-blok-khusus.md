# 0008. Edit langsung soal HOTS, stimulus, dan blok khusus

- Status: selesai
- Tanggal: 2026-11-03
- ADR terkait: [0012](../adr/0012-stimulus-bertipe-data-dulu-render-di-klien.md). Dasar: [spec 0001](0001-pipeline-quizzer-plan-then-generate.md), [spec 0007](0007-stimulus-hots-bertingkat.md), [ADR 0008](../adr/0008-tabel-dua-mode-baca.md)

## Masalah

Guru memvalidasi semua keluaran AI sebelum sampai ke siswa, tetapi jalur perbaikannya tidak simetris (diperiksa di kode 2026-11-03):

- Soal LOTS (tanpa stimulus) hanya bisa diedit langsung (`PATCH /quizzer/teacher/soal/{id}`).
- Soal HOTS (ber-stimulus) hanya bisa diperbaiki lewat regenerasi dengan feedback ke AI; PATCH menolaknya. Stimulus (teks, tabel, gambar SVG) tidak bisa diedit tangan sama sekali, padahal spec 0007 menjanjikannya.
- Blok teks dan heading bisa diedit langsung, tetapi lewat endpoint bernama `bulk-regenerate/text` yang sebenarnya hanya menyimpan teks. Blok rumus, tabel, dan gambar hanya bisa diperbaiki lewat AI dengan feedback.

Akibatnya kesalahan kecil (salah ketik, angka keliru, kunci meleset, satu sel tabel) di soal HOTS atau blok khusus memaksa guru memakai AI yang tidak deterministik dan bisa merusak bagian lain. Bila regenerasi tetap salah, guru tersangkut.

## Perilaku yang diharapkan

1. Guru bisa mengedit langsung soal HOTS (soal, opsi, kunci, langkah, kesimpulan) dengan field yang sama seperti soal LOTS.
2. Guru bisa mengedit stimulus soal HOTS pada bentuk aslinya: teks (sumber dengan LaTeX), tabel (judul, kolom, sel), atau gambar (SVG), beserta `narasi` untuk jenis bertipe. Jenis stimulus tidak bisa diganti lewat edit.
3. Setelah stimulus diedit, server menurunkan ulang teks bacaan dengan kode yang sama seperti pipeline (verbalizer untuk rumus, linearisasi untuk tabel, render lalu deskripsi vision untuk gambar). Bila turunan gagal (SVG tidak bisa dirender, spesifikasi tidak valid), tidak ada yang disimpan dan guru menerima pesan yang menyebut masalahnya.
4. Stimulus dipakai bersama satu cluster soal. Setelah stimulus diedit, semua soal di cluster diverifikasi ulang (jawab buta dan audit) dan `review_priority` serta `validation_notes` masing-masing diperbarui. `review_status` stimulus dan soal menjadi `edited`.
5. Guru bisa mengedit langsung blok khusus:
   - rumus: mengganti `source_markup` (LaTeX), bacaan diturunkan ulang lewat verbalizer; atau menimpa `readable_text` langsung;
   - tabel: mengganti `tabel` terstruktur, bacaan, ringkasan, dan telusur diturunkan ulang tanpa LLM kecuali untuk rumus di dalam sel;
   - gambar: menimpa `readable_text` (deskripsi).
   Bila `readable_text` dan sumber dikirim bersamaan, `readable_text` yang dipakai.
6. Teks bacaan yang ditulis tangan (soal, stimulus, blok) harus lolos pemeriksaan bacaan layar (`manual_reading_issues`, `plain_text_issues`): tanpa markdown dan tanpa simbol atau rumus mentah (termasuk `÷ ∪ ² < >`, perintah LaTeX, `km/jam`) di luar rumus `$...$`. Yang gagal ditolak dan pesannya menyebut potongan yang bermasalah. Narasi lama stimulus bertipe yang tidak bisa dipulihkan saat `narasi` tidak dikirim tidak dibuang diam-diam: soal di cluster diberi penanda di `validation_notes`. Bacaan blok tabel yang diganti tanpa `tabel` baru diberi peringatan di `issues` (ringkasan dan mode telusur masih dari tabel lama).
7. Regenerasi dengan feedback ke AI untuk soal HOTS dan blok khusus tidak berubah.

## Di luar cakupan

- Regenerasi dengan feedback ke AI untuk soal LOTS (belum ada; `revise_soal` bisa dipakai ulang nanti).
- Mengganti jenis stimulus (teks, tabel, gambar) lewat edit.
- Pengaman untuk modul yang sudah publish (blok Annoter tetap bisa diedit; perilaku sekarang dipertahankan). Pengaman untuk soal Quizzer sudah dikerjakan (revisi 2026-11-03): soal, stimulus, dan regenerasi hanya boleh pada kuis draft yang belum dikerjakan siswa mana pun (kunci terkunci saat publish; kuis yang sudah dikerjakan tidak bisa dikembalikan ke draft), selain itu 400.
- Persetujuan per soal (`approved`, `rejected`): belum ada endpoint pengisinya, tidak dikerjakan di sini.
- Antarmuka guru (frontend belum dimulai).

## Perubahan data

Tidak ada migrasi. Kolom yang dibutuhkan sudah ada: `soal.review_status` dan `soal_stimulus.review_status` sudah mengizinkan `edited`; `soal_stimulus.jenis`, `spesifikasi`, `source_markup`, `readable_text`, `ringkasan`, `tabel`; `blocks.readable_text`, `source_markup`, `ringkasan`, `tabel`, `review_priority`.

## Perubahan API

Semua peran TEACHER dengan pemeriksaan kepemilikan yang sudah ada (`_ensure_soal_owner`, `get_teacher_blocks`). Respons dibungkus `Response[T]`; error berbentuk `detail` dan `errors`.

1. `PATCH /quizzer/teacher/soal/{soal_id}`: pembatasan "hanya soal tanpa stimulus" dicabut. Request dan respons tidak berubah.
2. `PATCH /quizzer/teacher/soal/{soal_id}/stimulus` (baru). Request, salah satu bentuk menurut jenis stimulus soal itu:
   - teks: `source_markup` (string);
   - tabel atau gambar: `narasi` (opsional) dan `spesifikasi` (bentuk mentah; kunci turunan seperti `deskripsi` diabaikan dan diturunkan ulang).
   Respons: `Response[list[SoalResponse]]` (seluruh cluster setelah diperbarui). Error 400 dengan daftar masalah bila spesifikasi tidak valid atau gambar tidak bisa dirender; 403 bila bukan pemilik; 404 bila soal atau stimulus tidak ada.
3. `PATCH /annoter/blocks/{block_id}` (baru). Request: `readable_text`, `source_markup` (rumus), `tabel` (tabel), semuanya opsional dan minimal satu terisi. Respons: `Response[BlockEditResponse]` berisi `block_id`, `block_type`, `readable_text`, `ringkasan`, `tabel`, `review_priority`, dan `issues`. `bulk-regenerate/text` tetap ada demi kompatibilitas.

Sinkron ke koleksi Postman "Lydera" lewat `api-contract-sync` (butuh persetujuan sebelum menulis ke cloud).

## Perubahan AI

Tidak ada prompt atau `PROMPT_VERSION` yang berubah. Panggilan model yang dipicu edit: verbalizer rumus (saat sumber rumus diganti), deskripsi vision (saat gambar stimulus diedit), dan verifikasi validator (soal yang diedit dan soal sibling bila stimulus berubah). Semuanya dipanggil dari service backend lewat `asyncio.to_thread` ke fungsi `ai-services`, tanpa jalur baru ke database.

## Aksesibilitas

- Teks bacaan hasil edit tangan lewat pemeriksaan yang sama dengan keluaran AI (`speakable`, `has_raw_notation`, `latex_issues`), jadi siswa tidak menerima markdown atau simbol mentah.
- Bila bacaan diturunkan dari sumber, bacaan selalu setia pada sumber yang baru; bila guru menimpa `readable_text` langsung, bacaan bisa menyimpang dari sumbernya dan hanya guru yang menanggungnya (blok tidak punya verifikator).

## Verifikasi

- Tes murni di `backend/tests` dan `ai-services/tests`: edit soal HOTS diterima; stimulus teks, tabel, dan gambar diturunkan ulang (vision dan verbalizer dengan mock); gambar tidak bisa dirender tidak menyimpan apa pun; seluruh cluster diverifikasi ulang; teks bacaan dengan markdown atau simbol mentah ditolak; blok rumus, tabel, dan gambar diedit dengan dan tanpa `readable_text`.
- `uv run pytest -q` dari root hijau.
- Tinjauan `lydera-reviewer` (batas ai-services dan backend, otorisasi) dan `a11y-reviewer` (bacaan hasil edit).
- Tidak ada putaran Azure tanpa perintah.
