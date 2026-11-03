import json

from common.prompt_format import build_input, build_prompt
from common.image_prompts import (
    DESCRIPTION_STYLE_RULES, IMAGE_CONTEXT, IMAGE_OUTPUT, IMAGE_ROLE, IMAGE_RULES, IMAGE_TASK, KIND_COMMON_RULES, KIND_OUTPUT,
    KIND_RULES, NO_OPENER_RULE, VISUAL_EVIDENCE_RULES, image_input, image_kind_system, image_system,
)
from common.formula import GREEK_RULE, PLAIN_TEXT_RULE, feedback_block, rules_with_feedback


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


def table_system(*, feedback: bool = False) -> str:
    return build_prompt(
        role=TABLE_ROLE, task=TABLE_TASK, context=TABLE_CONTEXT,
        rules=rules_with_feedback(TABLE_RULES, feedback), output_format=TABLE_OUTPUT,
    )


def table_input(caption: str, table_html: str, feedback: str = "") -> str:
    return build_input(
        caption=caption,
        ocr_html=table_html,
        feedback_guru=feedback_block(feedback) if feedback else "",
        instruction="Bacakan tabel pada gambar terlampir sesuai aturan.",
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
