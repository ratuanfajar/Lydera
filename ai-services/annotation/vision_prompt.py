FOLLOW_IMAGE_RULES = (
    " Ikuti apa yang benar-benar tampak pada gambar; kalau keterangan atau konteks teks berbeda dari gambar "
    "(misalnya persamaan tidak cocok dengan titik atau garis yang tergambar), tulis yang tampak pada gambar dan jangan menyalin dari teks. "
    "Untuk grafik, sebutkan judul dan label sumbu jika tertulis pada gambar, serta titik yang ditandai. "
    "Untuk ikon atau ilustrasi dekoratif, sebutkan saja benda yang digambar dalam satu kalimat tanpa menafsirkan maknanya."
)

STRUCTURED_SUFFIX = (
    ' Kerjakan dalam dua tahap dan keluarkan HANYA JSON: {"pengamatan": {"jenis": "...", "judul": "...", "label_sumbu": "...", '
    '"skala_sumbu": "...", "titik_atau_garis_ditandai": ["..."], "bentuk_kurva_atau_pola": "...", "angka_yang_terbaca": ["..."]}, '
    '"deskripsi": "..."}. Isi "pengamatan" lebih dulu dengan HANYA hal yang benar-benar tampak, lalu tulis "deskripsi" (aturan penulisan di atas) '
    "yang hanya boleh memakai isi pengamatan."
)
