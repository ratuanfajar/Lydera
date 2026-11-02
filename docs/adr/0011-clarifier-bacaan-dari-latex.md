# 0011. Clarifier: bacaan jawaban diturunkan dari LaTeX oleh verbalizer

- Status: diterima
- Tanggal: 2026-10-28

## Konteks

Clarifier mengembalikan satu teks `message` yang ditulis model sebagai narasi kata, termasuk rumus. Dua masalah: siswa yang melihat layar tidak mendapat rumus bergaya buku, dan keterbacaan rumus bergantung pada kepatuhan model terhadap aturan prompt. Pada uji (F-054) pengelompokan "kuadrat dari selisih x dan h" benar 2 dari 3 ulangan; satu ulangan memberi "selisih x dan h kuadrat" yang ambigu bila hanya didengar. Quizzer sudah memisahkan tampilan (LaTeX) dari bacaan (kata) dengan verbalizer berbasis aturan dan pemeriksa struktur (ADR 0007). Spec: [0006](../specs/0006-clarifier-rumus-tampil-dan-bacaan.md).

## Keputusan

- Model menulis rumus di `summary` dalam LaTeX `$...$`. Kode menurunkan `message` (bacaan, tanpa `$` dan tanpa simbol mentah) dan `message_markup` (teks yang sama dengan LaTeX untuk ditampilkan) lewat `clarifier/speech.derive_message`, yang memakai verbalizer bersama (`common/math_text.readable_texts`).
- Bila LaTeX tidak valid atau verbalizer melaporkan temuan, `message_markup` bernilai `null` dan bacaan memakai hasil terbaik tanpa tanda dolar; temuan dicatat di log. Rumus rusak tidak pernah ditampilkan.
- `message` tetap berarti teks bacaan, sehingga klien lama tidak rusak. Tidak ada saklar env: bacaan selalu diturunkan, dan `message_markup` hanya tambahan.
- Argumen `compose_answer` diparse dengan `parse_json(latex=True)` supaya perintah LaTeX berbackslash tunggal (`\frac`, `\times`) tidak menjadi karakter kontrol JSON.
- Bidang lain (`label`, `justification`, `suggested_questions`) tetap tanpa rumus, dan `sources[].evidence` tetap teks sumber apa adanya (rumus di PDF terpotong, tidak aman dijadikan LaTeX).
- Data: `chat_messages.content_markup` Text nullable (migrasi `0d3e13679f93`). Riwayat untuk model memakai `content_markup` bila ada.

## Konsekuensi

- Pengelompokan rumus tidak lagi bergantung pada prompt: uji live 3 ulangan x 2 pertanyaan rumus memberi pengelompokan benar 6 dari 6 ("buka kurung x dikurangi h tutup kurung pangkat dua", "akar kuadrat dari satu ditambah m pangkat dua selesai akar"). Gaya bacaan sama dengan Quizzer dan Annoter.
- Bacaan lebih panjang dan lebih eksplisit daripada narasi buatan model ("buka kurung ... tutup kurung"); itu pilihan ADR 0007 (kurung disebut bila perlu mencegah ambigu).
- Setiap rumus unik dalam jawaban menambah satu panggilan verbalizer kecil (di-cache, paralel).
- Verifikasi sitasi tidak mencakup isi rumus di `summary` (F-055); rumus yang dikutip dari sumber luar yang salah tetap tampil rapi. Aturan prompt "jangan memperbaiki sumber sendiri" tetap berlaku.
- Rendering LaTeX dan semantik (label = `message`, rumus visual dikecualikan dari pembaca layar) menunggu frontend. Klien yang merender `message_markup` harus membatasi perintah LaTeX yang boleh dirender.
- Alternatif yang ditolak: saklar env seperti `QUIZ_MARKUP_ENABLED` (tidak ada alasan menahan bacaan deterministik), dan meminta model menulis dua versi sekaligus (bisa tidak sinkron).

## Pembaruan: review kode dan aksesibilitas

Temuan yang diterapkan: kegagalan verbalizer tidak lagi menggagalkan giliran chat (bacaan darurat tanpa LaTeX, markup `null`); bacaan darurat mengganti simbol dengan kata dan tidak pernah memuat sintaks LaTeX; daftar putih perintah LaTeX, batas 10 rumus dan 4.000 karakter, deteksi pangkat atau subskrip tanpa isi (kasus nyata: `$90^$ derajat` terbaca "sembilan puluh pangkat derajat"), dan deteksi simbol di luar tanda dolar; `label`, `justification`, dan `suggested_questions` dibersihkan di kode; `summary` bukan string atau kosong memakai pesan cadangan; semua jalur hasil agen membawa kunci baru; kegagalan Redis saat menyimpan riwayat tidak menggagalkan jawaban; `parse_json(latex=True)` hanya bila argumen memuat `$`; contoh titik di prompt diganti (koordinat dalam LaTeX terpisah), aturan uang dan rumus panjang di kalimat sendiri ditambahkan.

Belum dikerjakan: perbaikan verbalizer bersama (F-056) dan uji dengar nyata. Keputusan yang diambil sadar: tidak ada saklar env seperti `QUIZ_MARKUP_ENABLED`, karena bacaan deterministik lebih baik daripada narasi buatan model; konsekuensinya Clarifier merilis jalur ini sebelum uji dengar, dan saklar bisa ditambah satu baris bila ingin menahannya.
