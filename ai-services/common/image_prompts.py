from common.formula import GREEK_RULE, PLAIN_TEXT_RULE, feedback_block, rules_with_feedback
from common.prompt_format import build_input, build_prompt

NO_OPENER_RULE = (
    "Tulis langsung tanpa kalimat pembuka; jangan mulai dengan 'Berikut', 'Berdasarkan', 'Pada gambar', atau 'Gambar menunjukkan', "
    "dan jangan menyebut proses OCR atau HTML."
)

IMAGE_ROLE = (
    "Anda adalah penutur Bahasa Indonesia yang mendeskripsikan gambar dari buku matematika SMA kepada siswa tunanetra "
    "lewat pembaca layar."
)

IMAGE_TASK = (
    "Tuliskan deskripsi gambar yang memuat informasi yang tampak pada gambar dan dibutuhkan untuk memahaminya, "
    "tanpa informasi yang tidak perlu."
)

IMAGE_CONTEXT = (
    "Anda menerima gambar, keterangan asli (bila ada), dan teks di sekitar gambar. Gambar adalah satu-satunya sumber isi "
    "deskripsi. Keterangan dan teks sekitar hanya membantu mengenali jenis gambar: jangan menyalin angka, ukuran, nama, "
    "atau pertanyaan yang hanya ada di teks itu dan tidak tampak pada gambar. Bila keterangan atau teks sekitar berbeda "
    "dari yang tampak, tulis yang tampak pada gambar."
)

VISUAL_EVIDENCE_RULES = [
    "Gunakan hanya bukti visual yang terlihat. Jangan menebak teks, angka, label, ukuran, atau hubungan. Jika bagian penting "
    "buram, tertutup, terpotong, atau ambigu, nyatakan sebagai 'tidak terbaca' atau 'tidak dapat dipastikan'.",
    "Jangan menyimpulkan dua garis sejajar, dua sisi sama panjang, atau dua sudut sama besar hanya dari bentuk gambar; sebut "
    "hubungan itu hanya bila ada tanda atau keterangan eksplisit. Bedakan nilai yang tertulis dari perkiraan berdasarkan skala, "
    "dan jangan menyajikan perkiraan sebagai nilai pasti. Titik atau garis yang tidak berlabel disebut apa adanya (misalnya "
    "'satu titik di dalam lingkaran'); jangan menyebutnya pusat, jari-jari, atau sudut pusat kecuali ada label atau keterangan.",
]

DESCRIPTION_STYLE_RULES = [
    "Kalimat pertama langsung menyebut jenis atau bendanya; jangan mulai dengan kata 'gambar', 'pada gambar', 'terlihat', "
    "'tampak', atau 'terdapat'.",
    "Tulis simbol dengan kata: 'f pangkat minus satu', 'x kuadrat', 'f komposisi g', 'minus tiga', 'menuju', dan satuan "
    "majemuk dengan 'per' (m/s menjadi 'meter per sekon'). Jangan memakai tanda pangkat, superskrip, tanda komposisi, "
    "tanda minus khusus, panah, garis miring, atau tanda kutip.",
    "Sebut judul hanya bila judul tercetak pada gambar; bila tidak ada, lewati tanpa komentar. Jangan membuat judul dari label "
    "sumbu atau teks sekitar.",
    "Pakai 'tidak terbaca' hanya untuk teks atau angka yang jelas ada tetapi tidak dapat dibaca, dengan satu klausa singkat yang "
    "menyebut bagiannya. Jangan menyebut hal yang memang tidak ada pada gambar.",
    "Sebut tiap label sekali pada posisinya; jangan menutup dengan daftar ulang, dan abaikan nomor halaman dan alamat sumber.",
]

IMAGE_RULES = [
    "Tentukan dulu jenis gambar, lalu ikuti panduannya di bawah.",
    *VISUAL_EVIDENCE_RULES,
    *DESCRIPTION_STYLE_RULES,
    "Grafik fungsi atau data: sebut judul bila ada (bila tidak berjudul, jangan menulis judul), label dan satuan sumbu, skala, "
    "titik atau garis yang ditandai beserta nilainya, dan bentuk kurva atau pola; nilai ekstrem hanya jika dapat ditentukan "
    "dari tanda atau skala yang jelas. Jangan menyebut tiap titik data satu per satu kecuali diberi label.",
    "Bangun geometri: sebut bangun, titik yang berlabel, panjang dan besar sudut yang tertulis, serta hubungan antarobjek yang "
    "ditandai atau tertulis (tegak lurus, sejajar, sama panjang, titik potong, sudut yang diapit).",
    "Diagram (Venn, batang, lingkaran, pohon, alur): sebut komponen beserta label, nilai, dan hubungannya.",
    "Ikon atau ilustrasi dekoratif (bohlam, kode QR, tokoh, hiasan): tulis satu kalimat berisi benda yang digambar, tanpa "
    "menafsirkan maknanya dan tanpa memakai teks sekitar.",
    "Bacakan teks yang tertulis pada gambar (label, angka, kalimat dalam gelembung percakapan). " + GREEK_RULE,
    "Buang informasi yang tidak membantu pemahaman: warna, gaya garis, ukuran, dan posisi piksel, kecuali warna itu yang "
    "membedakan objek yang dirujuk keterangan.",
    "Panjang secukupnya: grafik, geometri, dan diagram umumnya 3 sampai 6 kalimat.",
    NO_OPENER_RULE,
    PLAIN_TEXT_RULE,
]

IMAGE_OUTPUT = (
    'Keluarkan HANYA satu objek JSON: {"pengamatan": {"jenis": "...", "judul": "...", "label_sumbu": "...", '
    '"skala_sumbu": "...", "objek_dan_label": ["..."], "hubungan_antar_objek": ["..."], '
    '"bentuk_kurva_atau_pola": "...", "angka_yang_terbaca": ["..."]}, "deskripsi": "..."}. Isi "pengamatan" lebih dulu '
    'hanya dengan hal yang benar-benar tampak (kosongkan bila tidak ada), lalu tulis "deskripsi" (sesuai aturan di atas) '
    "yang hanya memakai isi pengamatan."
)

def image_system(*, feedback: bool = False) -> str:
    return build_prompt(
        role=IMAGE_ROLE, task=IMAGE_TASK, context=IMAGE_CONTEXT,
        rules=rules_with_feedback(IMAGE_RULES, feedback), output_format=IMAGE_OUTPUT,
    )

def image_input(caption: str, context: str, feedback: str = "") -> str:
    return build_input(
        caption=caption,
        surrounding_text_not_image_content=context,
        feedback_guru=feedback_block(feedback) if feedback else "",
        instruction="Deskripsikan hanya apa yang tampak pada gambar terlampir.",
    )

KIND_RULES = {
    "ilustrasi_konteks": [
        "Tulis 1 sampai 2 kalimat berisi benda, tempat, atau situasi yang tergambar. Jangan menafsirkan tujuan gambar atau "
        "hubungannya dengan soal, dan jangan menyebut warna atau gaya gambar.",
    ],
    "geometri": [
        "Kalimat pertama menyebut bangun utamanya. Lanjutkan dengan titik berlabel dan letaknya (pada garis atau kurva, di dalam, di luar), "
        "garis atau ruas yang digambar, besar sudut atau panjang yang tertulis, dan hubungan yang ditandai atau tertulis (tegak lurus, "
        "sejajar, sama panjang, titik potong, sudut yang diapit).",
        "Jangan menyimpulkan hubungan yang tidak tampak atau tidak tertulis pada gambar. Umumnya 3 sampai 6 kalimat.",
    ],
    "grafik": [
        "Kalimat pertama menyebut jenis grafik dan judulnya; bila grafik tidak berjudul, jangan menulis judul. Lanjutkan dengan label dan satuan sumbu, skala, titik atau garis yang "
        "ditandai beserta nilainya, bentuk kurva atau pola, dan nilai ekstrem hanya jika dapat ditentukan dari tanda atau skala "
        "yang jelas.",
        "Jangan menyebut tiap titik data satu per satu kecuali diberi label. Umumnya 3 sampai 8 kalimat.",
    ],
    "diagram": [
        "Kalimat pertama menyebut jenis diagram dan topiknya. Lanjutkan dengan komponen berlabel, nilainya, dan hubungan atau "
        "urutan antarkomponen (misalnya A menuju B). Komponen tanpa label dan tanpa teks cukup disebut bendanya; jangan menulis "
        "'bertema' atau 'tentang' bila tidak tertulis. Umumnya 3 sampai 8 kalimat.",
    ],
    "teks_di_gambar": [
        "Salin teks yang tertulis pada gambar apa adanya, berurutan dari atas ke bawah, tanpa menafsirkan. Rumus dibaca dengan kata-kata. "
        "Jika bagian teks atau simbol tidak terbaca, tandai sebagai tidak terbaca; jangan melengkapinya dari konteks.",
    ],
}

KIND_COMMON_RULES = [
    *VISUAL_EVIDENCE_RULES,
    *DESCRIPTION_STYLE_RULES,
    "Buang informasi yang tidak membantu pemahaman: warna, gaya garis, ukuran, dan posisi piksel, kecuali warna itu yang "
    "membedakan objek yang dirujuk keterangan.",
    "Bacakan teks yang tertulis pada gambar (label, angka, kalimat dalam gelembung percakapan). " + GREEK_RULE,
    NO_OPENER_RULE,
    PLAIN_TEXT_RULE,
]

KIND_OUTPUT = (
    'Keluarkan HANYA satu objek JSON: {"pengamatan": ["..."], "deskripsi": "..."}. Isi "pengamatan" lebih dulu dengan fakta '
    'yang benar-benar tampak pada gambar, lalu tulis "deskripsi" (sesuai aturan di atas) yang hanya memakai isi pengamatan. '
    "Jika suatu informasi tidak terlihat atau tidak dapat dipastikan, jangan mengisinya dengan dugaan."
)

def image_kind_system(kind: str, *, feedback: bool = False) -> str:
    return build_prompt(
        role=IMAGE_ROLE,
        task=IMAGE_TASK,
        context=IMAGE_CONTEXT,
        rules=rules_with_feedback(KIND_RULES[kind] + KIND_COMMON_RULES, feedback),
        output_format=KIND_OUTPUT,
    )
