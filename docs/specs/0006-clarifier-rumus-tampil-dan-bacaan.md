# 0006. Clarifier: rumus tampil normal, bacaan narasi

- Status: selesai
- Tanggal: 2026-10-28
- ADR terkait: dibuat saat selesai; dasar: [0007](../adr/0007-verbalizer-rumus-gaya-kelas-dengan-pemeriksa-struktur.md), [0010](../adr/0010-clarifier-pencarian-hibrida-dan-sumber-oer.md)

## Masalah

Jawaban Clarifier hanya berupa narasi kata ("kuadrat dari selisih x dan h, tambah ..."). Siswa awas atau low-vision yang melihat layar tidak mendapat rumus bergaya buku, dan siswa tunanetra bergantung pada kepatuhan model terhadap aturan verbalisasi di prompt. Hasil uji (F-054): pengelompokan "kuadrat dari selisih x dan h" benar pada 2 dari 3 ulangan; satu ulangan "selisih x dan h kuadrat" yang ambigu bila hanya didengar. Quizzer sudah memisahkan rumus tampil (LaTeX) dan bacaan (kata) lewat verbalizer berbasis aturan dengan pemeriksa struktur.

## Perilaku yang diharapkan

1. Model menulis rumus di `summary` dalam LaTeX di antara tanda dolar (mis. `$(x - h)^2 + (y - k)^2 = r^2$`). Di luar `$...$` hanya kata dan bilangan biasa.
2. Backend mengembalikan dua bentuk untuk satu jawaban:
   - `message`: teks bacaan, rumus sudah diubah menjadi kata oleh verbalizer yang sama dengan Quizzer; tanpa `$` dan tanpa simbol mentah. Ini yang dibacakan pembaca layar.
   - `message_markup`: teks yang sama dengan LaTeX `$...$` untuk ditampilkan; `null` bila jawaban tanpa rumus.
3. Klien lama yang hanya memakai `message` tetap benar: `message` selalu teks bacaan.
4. Bila LaTeX dari model bermasalah, `message_markup` bernilai `null`, masalah dicatat di log, dan `message` memakai bacaan darurat: tanda `$` dan sintaks LaTeX (garis miring terbalik, kurung kurawal, `^`, `_`) tidak pernah sampai ke bacaan, simbol umum diganti kata ('sama dengan', 'tambah', 'pangkat', 'derajat'), dan pecahan menjadi 'a per b'. Yang dianggap bermasalah: `$` tidak berpasangan, rumus kosong, kurung tidak seimbang, pangkat atau subskrip tanpa isi (mis. `90^`), perintah LaTeX di luar daftar putih (mis. href, url, includegraphics, input), lebih dari 10 rumus atau lebih dari 4.000 karakter, simbol matematika di luar tanda dolar, temuan pemeriksa verbalizer, dan kegagalan verbalizer (error API setelah retry). Rumus yang rusak tidak pernah ditampilkan, dan jawaban tidak pernah gagal total karena verbalizer.
5. `suggested_questions`, `label`, dan `justification` tidak memuat rumus: ditulis dengan kata, dan kode membersihkannya (tanpa `$` dan simbol mentah) sebelum dikembalikan. Argumen `summary` yang bukan string atau kosong memakai pesan cadangan. Semua jalur hasil agen membawa `message_markup` dan `format_issues`.
6. `sources[].evidence` tetap teks biasa dari sumber (rumus di PDF sering terpotong dan tidak aman dijadikan LaTeX).
7. Riwayat: setiap pesan asisten menyimpan `content` (bacaan) dan `content_markup` (nullable). Riwayat percakapan yang dikirim ke model memakai `content_markup` bila ada, supaya model melanjutkan konvensi yang sama.
8. Aturan verbalisasi manual di prompt (pengelompokan rumus, kata operasi) dihapus untuk `summary` karena ditangani verbalizer; aturan tanpa markdown, tanpa pembuka meta, panjang kalimat, bahasa Indonesia, dan sumber luar tidak berubah.

## Di luar cakupan

- Rendering LaTeX di frontend dan semantik Flutter (frontend belum dimulai); spec ini hanya menyiapkan kontrak (lihat Aksesibilitas).
- Perbaikan verbalizer bersama (titik bernama seperti `C(h, k)` dibaca 'titik C dengan koordinat h dan k'; plus-minus dibaca 'plus atau minus'; kata 'koma' antar koordinat) karena mengubah `FORMULA_PROMPT_VERSION` dan cache Annoter dan Quizzer; dicatat F-056.
- LaTeX pada `evidence`, `label`, `justification`, dan `suggested_questions`.
- Mengubah verbalizer (ADR 0007) atau prompt pencarian.
- Mengisi ulang pesan lama dengan `content_markup`.

## Perubahan data

Satu migrasi Alembic: `chat_messages.content_markup` Text nullable. Baris lama tetap valid (`null`). Hanya dijalankan di DB dev setelah diuji naik dan turun.

## Perubahan API

`POST /clarifier/sessions/{session_id}/messages`: respons bertambah `message_markup: str | null`. `GET /clarifier/sessions/{session_id}/messages`: tiap pesan bertambah `content_markup: str | null`. Tidak ada field yang dihapus atau berubah arti (`message` dan `content` tetap teks bacaan). Postman disinkronkan lewat `api-contract-sync`.

## Perubahan AI

- `clarifier/speech.py` (baru): `derive_message(text) -> (spoken, markup, issues)`; memakai `common.math_text` (`latex_issues`, `readable_texts`); teks tanpa `$` dikembalikan apa adanya dengan `markup` `None`.
- `agent._finalize`: menurunkan `message` dan `message_markup` dari `summary`; menyertakan `format_issues` di hasil untuk log.
- Prompt dan deskripsi `summary` di `tools.py`: aturan LaTeX di `summary`, kata biasa di bidang lain; aturan pengelompokan manual dihapus. Model dan effort tidak berubah; `PROMPT_VERSION` tidak berlaku (bukan prompt anotasi).
- Biaya: satu panggilan verbalizer kecil per rumus unik per jawaban (di-cache oleh `common.cache`, paralel).

## Aksesibilitas

- Frontend merender `message_markup` secara visual dan memberi `Semantics(label: message)` pada blok itu dengan rumus visual dikecualikan dari pembaca layar (`ExcludeSemantics`), seperti rencana Quizzer; teks yang dibacakan selalu `message`.
- Pengelompokan ("kuadrat dari selisih x dan h") dihasilkan aturan verbalizer, bukan kepatuhan model.
- Risiko: LaTeX model bisa salah; pemeriksa struktur menangkap sebagian, dan jawaban dengan temuan jatuh ke bacaan darurat tanpa tampilan rumus. Kualitas bacaan belum diuji dengar dengan siswa atau guru SLB; hasil uji LLM bukan bukti bahwa bacaan terdengar jelas.

Kontrak untuk klien (Flutter):
- Bubble jawaban asisten: `Semantics(label: message, container: true, excludeSemantics: true)` membungkus teks campur widget rumus dari `message_markup`; label selalu `message`. Jangan memberi `Semantics` hanya pada widget rumus (bacaan ganda), dan jangan membacakan atau menampilkan string `message_markup` mentah.
- `message_markup` null: tampilkan `Text(message)` biasa. Bila renderer LaTeX gagal, tampilkan `Text(message)`, jangan LaTeX mentah.
- Renderer LaTeX tidak boleh memakai mode yang mempercayai perintah (href, url, includegraphics); server sudah memfilter dengan daftar putih, tetapi klien tetap membatasi.
- Riwayat: aturan sama dengan `content_markup` dan label `content`.
- `sources`: tiap sumber satu node ('Sumber 1 dari 2, {label}. Alasan: {justification}'); `evidence` dilipat di balik kontrol 'Lihat kutipan' dan tidak dibacakan otomatis (bisa memuat simbol atau berbahasa Inggris); status `verified` ditulis dengan kata ('belum terverifikasi'), bukan warna atau ikon; `suggested_questions` berupa tombol.
- Umumkan jawaban baru satu kali; rumus visual mengikuti `textScaler` dan dapat digulir horizontal.

## Verifikasi

1. Tes pytest: `speech.derive_message` (tanpa rumus, satu rumus, banyak rumus, `$` tidak berpasangan, dolar ter-escape, rumus kosong, pangkat tanpa isi, daftar putih, batas jumlah dan panjang, simbol di luar tanda dolar, temuan dan kegagalan verbalizer), `_finalize` (kunci baru, summary bukan string, pembersihan label dan pertanyaan lanjutan, JSON dengan satu atau dua backslash), `agent.run` semua jalur, service backend dengan repo dan Redis palsu (markup tersimpan, riwayat, kegagalan Redis tidak menggagalkan jawaban), skema respons.
2. Migrasi di DB dev: naik, turun, naik; kolom ada dan nullable.
3. Alur nyata lewat API dan worker dev, 3 ulangan: persamaan lingkaran, garis singgung bergradien, pertanyaan rumus; periksa `message` tanpa `$` dan tanpa pengelompokan ambigu ("selisih x dan h kuadrat", "kurang h kuadrat"), `message_markup` berisi LaTeX yang seimbang, riwayat menyimpan keduanya.
4. Pertanyaan tanpa rumus: `message_markup` `null`.
5. Review `lydera-reviewer` dan `a11y-reviewer`, sinkron Postman, catat di findings (F-054).
