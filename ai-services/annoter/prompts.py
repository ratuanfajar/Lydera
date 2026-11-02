import json

from common.prompt_format import build_input, build_prompt
from common.formula import GREEK_RULE, PLAIN_TEXT_RULE, feedback_block, rules_with_feedback

NO_OPENER_RULE = (
    "Tulis langsung tanpa kalimat pembuka; jangan mulai dengan 'Berikut', 'Berdasarkan', 'Pada gambar', atau 'Gambar menunjukkan', "
    "dan jangan menyebut proses OCR atau HTML."
)

TABLE_ROLE = (
    "Anda adalah penutur Bahasa Indonesia yang membacakan tabel dari buku matematika SMA kepada siswa tunanetra "
    "lewat pembaca layar."
)

TABLE_TASK = (
    "Ubah tabel pada gambar menjadi tabel terstruktur, teks linear yang dapat dipahami hanya dengan mendengarkan, "
    "dan satu kalimat topik."
)

TABLE_CONTEXT = (
    "Anda menerima gambar tabel, keterangan (bila ada), dan HTML hasil OCR yang mungkin memuat sel rusak, kosong, "
    "atau salah baca. Gambar adalah sumber yang benar."
)

TABLE_RULES = [
    "Isi 'kolom' dengan judul kolom dari baris judul, dan 'baris' dengan semua baris data di bawahnya; setiap baris punya "
    "jumlah sel yang sama dengan jumlah kolom. Perbaiki sel yang jelas salah OCR berdasarkan gambar; tidak boleh ada nilai "
    "yang hilang atau ditambah.",
    "Sel gabungan ditulis nilainya pada setiap sel yang tercakup. Judul kolom bertingkat (judul gabungan di atas sub-judul) "
    "digabung menjadi satu judul per kolom, mis. 'Nilai UTS' dan 'Nilai UAS'. Bila tabel tidak punya baris judul, isi 'kolom' "
    "dengan 'Kolom 1', 'Kolom 2', dan seterusnya dan masukkan semua baris ke 'baris'. Sel yang memang kosong pada gambar "
    "ditulis dengan string kosong di 'baris'; sel yang ada tulisannya tetapi tidak terbaca ditulis 'tidak terbaca', jangan "
    "ditukar. Bila tabel tidak punya judul tercetak, isi 'judul' dengan string kosong; jangan menulis 'tidak ada'.",
    "Angka dan teks biasa di sel ditulis apa adanya. Ekspresi matematika di sel (pangkat, akar, pecahan, pertidaksamaan) "
    "ditulis sebagai LaTeX di antara tanda dolar, mis. $x^{2}$ atau $\\frac{1}{2}$; sistem mengubahnya menjadi kata.",
    "Jika teks, angka, simbol, atau sel tidak dapat dibaca dengan yakin, jangan menebak: tulis 'tidak terbaca' pada sel itu "
    "dan pertahankan posisinya. Selain memperbaiki salah OCR berdasarkan gambar, jangan mengubah, melengkapi, atau "
    "menyimpulkan nilai dari pola tabel, HTML OCR, pengetahuan umum, atau konteks soal.",
    "'deskripsi' adalah bacaan lengkap seluruh sel, bukan ringkasan: sebut judul kolom lebih dulu, lalu setiap baris berurutan "
    "dengan awalan nomor baris dan pasangan 'nama kolom: nilai' dipisah titik koma, mis. 'Baris 1. Nama: Ani; Nilai: 80.'; sel "
    "yang kosong disebut 'kosong'. Jangan menafsirkan, merangkum tren, atau menjelaskan isi tabel di 'deskripsi'.",
    "'topik' adalah satu kalimat pendek tentang apa isi tabel, diawali 'Tabel ini' atau 'Tabel tentang'. Jangan menyebut "
    "jumlah kolom atau baris, nama kolom, nilai sel, tren, atau jawaban.",
    GREEK_RULE,
    NO_OPENER_RULE + " Jangan menyebut 'tabel tersebut' atau 'gambar yang diberikan'.",
    PLAIN_TEXT_RULE,
]

TABLE_OUTPUT = (
    'Keluarkan HANYA satu objek JSON: {"pengamatan": {"judul": "...", "kolom": ["..."], "baris": [["..."]], '
    '"sel_dikoreksi": ["..."]}, "deskripsi": "...", "topik": "..."}. Isi "pengamatan" lebih dulu hanya dengan hal '
    'yang benar-benar tampak pada gambar, lalu tulis "deskripsi" dan "topik" (sesuai aturan di atas) yang hanya '
    "memakai isi pengamatan. Gunakan tipe data sesuai contoh: string untuk judul/sel, array untuk kolom/baris/sel_dikoreksi."
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


def table_system(*, feedback: bool = False) -> str:
    return build_prompt(
        role=TABLE_ROLE, task=TABLE_TASK, context=TABLE_CONTEXT,
        rules=rules_with_feedback(TABLE_RULES, feedback), output_format=TABLE_OUTPUT,
    )


def image_system(*, feedback: bool = False) -> str:
    return build_prompt(
        role=IMAGE_ROLE, task=IMAGE_TASK, context=IMAGE_CONTEXT,
        rules=rules_with_feedback(IMAGE_RULES, feedback), output_format=IMAGE_OUTPUT,
    )


def table_input(caption: str, table_html: str, feedback: str = "") -> str:
    return build_input(
        caption=caption,
        ocr_html=table_html,
        feedback_guru=feedback_block(feedback) if feedback else "",
        instruction="Bacakan tabel pada gambar terlampir sesuai aturan.",
    )


def image_input(caption: str, context: str, feedback: str = "") -> str:
    return build_input(
        caption=caption,
        surrounding_text_not_image_content=context,
        feedback_guru=feedback_block(feedback) if feedback else "",
        instruction="Deskripsikan hanya apa yang tampak pada gambar terlampir.",
    )


IMAGE_KINDS = ("dekoratif", "ilustrasi_konteks", "geometri", "grafik", "diagram", "teks_di_gambar")

KIND_DEFINITIONS = [
    "dekoratif: ikon penanda bagian buku, logo, kode QR, atau hiasan yang tidak mengajarkan apa pun dan tidak dibutuhkan untuk memahami materi atau soal.",
    "ilustrasi_konteks: foto atau gambar situasi nyata (benda, tempat, orang, potret tokoh) yang melatari cerita atau pembahasan.",
    "geometri: bangun atau konstruksi geometri dengan titik, garis, sudut, atau lingkaran, termasuk gambar situasi yang diberi titik dan garis berlabel.",
    "grafik: bidang koordinat, kurva fungsi, atau grafik data (batang, garis, histogram, lingkaran data).",
    "diagram: diagram Venn, pohon, alur, peta konsep, skema, atau struktur visual lain yang bukan grafik data dan bukan bangun geometri.",
    "teks_di_gambar: gambar yang isi utamanya teks, rumus, percakapan, atau soal.",
    "Jika gambar memuat beberapa jenis elemen, pilih kategori yang paling dominan; elemen penting dari kategori lain tetap disebut dalam deskripsi.",
    "Jika gambar terlalu buram atau terpotong untuk diklasifikasikan, pilih kategori yang paling mendekati dengan skor yakin rendah.",
]

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

CLASSIFIER_OUTPUT = (
    'Keluarkan HANYA JSON: {"jenis": "salah satu dari: ' + ", ".join(IMAGE_KINDS) + '", "yakin": 1 sampai 5, "alasan": "satu kalimat"}. '
    "Skor yakin: 1 = sangat tidak yakin, 2 = kurang yakin, 3 = cukup yakin, 4 = yakin, 5 = sangat yakin; skor mencerminkan "
    "kejelasan bukti visual."
)


def image_classifier_system() -> str:
    return build_prompt(
        role="Anda adalah pengklasifikasi gambar dari buku matematika SMA untuk keperluan aksesibilitas siswa tunanetra.",
        task="Tentukan satu jenis untuk gambar yang diberikan.",
        context="Jenis menentukan cara gambar dideskripsikan. Teks sekitar (bila ada) hanya petunjuk, bukan isi gambar.",
        rules=KIND_DEFINITIONS,
        output_format=CLASSIFIER_OUTPUT,
    )


def image_classifier_input(caption: str, context: str = "") -> str:
    return build_input(
        caption=caption,
        surrounding_text_not_image_content=context,
        instruction="Klasifikasikan gambar terlampir.",
    )


def image_kind_system(kind: str, *, feedback: bool = False) -> str:
    return build_prompt(
        role=IMAGE_ROLE,
        task=IMAGE_TASK,
        context=IMAGE_CONTEXT,
        rules=rules_with_feedback(KIND_RULES[kind] + KIND_COMMON_RULES, feedback),
        output_format=KIND_OUTPUT,
    )


def image_arbiter_system() -> str:
    return build_prompt(
        role="Anda adalah penentu akhir klasifikasi gambar dari buku matematika SMA untuk keperluan aksesibilitas siswa tunanetra.",
        task="Tentukan keputusan final satu jenis untuk gambar yang diberikan.",
        context=(
            "Anda menerima gambar dan dua klasifikasi awal: percobaan 1 dibuat tanpa teks sekitar, percobaan 2 dengan teks sekitar. "
            "Teks sekitar hanya petunjuk, bukan isi gambar."
        ),
        rules=KIND_DEFINITIONS + [
            "Periksa gambar secara mandiri. Pakai dua klasifikasi awal hanya sebagai pembanding, bukan fakta; keputusan Anda final "
            "dan boleh berbeda dari keduanya.",
            "Jika bukti visual tidak cukup, pilih kategori paling mendekati dengan skor yakin rendah; jangan mengarang isi gambar.",
            "Bila ragu antara dekoratif dan ilustrasi_konteks, pilih ilustrasi_konteks: salah membuang gambar yang penting lebih "
            "merugikan daripada mendeskripsikan gambar yang tidak penting.",
        ],
        output_format=CLASSIFIER_OUTPUT,
    )


def image_arbiter_input(caption: str, context: str, first: dict, second: dict) -> str:
    return build_input(
        caption=caption,
        surrounding_text_not_image_content=context,
        percobaan_1_tanpa_konteks=json.dumps(first, ensure_ascii=False),
        percobaan_2_dengan_konteks=json.dumps(second, ensure_ascii=False),
        instruction="Tentukan keputusan final klasifikasi gambar terlampir.",
    )
