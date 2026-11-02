import pytest

from annoter import speakable as module
from annoter.speakable import speakable


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Kecepatan (m/s) naik.", "Kecepatan (meter per sekon) naik."),
        ("Laju 60 km/jam.", "Laju 60 kilometer per jam."),
        ("Debit L/menit.", "Debit liter per menit."),
        ("Dari 2 s/d 5.", "Dari 2 sampai dengan 5."),
        ("Berlaku untuk dan/atau kasus lain.", "Berlaku untuk dan atau kasus lain."),
        ("Nilai x/y tetap.", "Nilai x per y tetap."),
        ("Pecahan 1/2 ditulis.", "Pecahan 1 per 2 ditulis."),
        ("Cek yang/atau tidak diubah.", "Cek yang/atau tidak diubah."),
    ],
)
def test_garis_miring_dibaca_per_atau_dipertahankan(text, expected):
    assert speakable(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ('Tulisan "Fungsi" di depan.', "Tulisan Fungsi di depan."),
        ("Teks “Diskon hingga” dan “50%”.", "Teks Diskon hingga dan 50%."),
        ("Label 'Jarak berhenti' tampak.", "Label Jarak berhenti tampak."),
        ("Titik A' dan B' berada di kanan.", "Titik A' dan B' berada di kanan."),
    ],
)
def test_tanda_kutip_dibuang_tetapi_aksen_titik_utuh(text, expected):
    assert speakable(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Suhu dari 60 sampai −60.", "Suhu dari 60 sampai minus 60."),
        ("Nilai -3 di sumbu.", "Nilai minus 3 di sumbu."),
        ("Kelas 10-19 berisi data.", "Kelas 10-19 berisi data."),
        ("Selisih 5 - 3 tetap.", "Selisih 5 - 3 tetap."),
        ("Fungsi f⁻¹ dan x² dan x³.", "Fungsi f pangkat minus satu dan x pangkat dua dan x pangkat tiga."),
        ("Fungsi f^-1 dan x^2 dan 2^{10}.", "Fungsi f pangkat minus satu dan x pangkat dua dan 2 pangkat 10."),
        ("Garis f ∘ g.", "Garis f komposisi g."),
        ("Panah A → B.", "Panah A menuju B."),
    ],
)
def test_notasi_matematika_ditulis_dengan_kata(text, expected):
    assert speakable(text) == expected


@pytest.mark.parametrize("text", ["Isi tabel ... dan seterusnya.", "Bagian yang harus diisi ….", "Kosong: ..."])
def test_elipsis_dipertahankan_apa_adanya(text):
    assert speakable(text) == text


def test_description_issues_menandai_notasi_mentah_dan_bagian_tidak_terbaca():
    assert module.description_issues("Kurva naik dari kiri ke kanan.") == []
    assert len(module.description_issues("Grafik y = x^2 membuka ke atas.")) == 1
    assert len(module.description_issues("Label sumbu tidak terbaca.")) == 1
    assert len(module.description_issues("Sumbu y = f(x) tidak dapat dibaca.")) == 2


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Percepatan 9 m/s² dan massa jenis 5 kg/m³.", "Percepatan 9 meter per sekon pangkat dua dan massa jenis 5 kilogram per meter pangkat tiga."),
        ("Kecepatan 60 km/jam dan 5 m/menit.", "Kecepatan 60 kilometer per jam dan 5 meter per menit."),
        ("Variabel m/n dan s/t serta L/P.", "Variabel m per n dan s per t serta L per P."),
        ("Pada waktu 0 s dan 9 s.", "Pada waktu 0 s dan 9 s."),
        ("Bilangan 2 1/2 dan tanggal 17/08/1945.", "Bilangan 2 1/2 dan tanggal 17/08/1945."),
        ("Fungsi 1/x dan x/2 serta 60/jam.", "Fungsi 1 per x dan x per 2 serta 60 per jam."),
        ("Turunan (fg)' dan (f+g)' ada.", "Turunan (fg)' dan (f+g)' ada."),
        ("Fungsi invers f-1 dan g-1.", "Fungsi invers f-1 dan g-1."),
        ("Satuan kg/orang dan km/h.", "Satuan kg/orang dan km/h."),
        ("Nilai x-1 tetap.", "Nilai x-1 tetap."),
        ("Titik (1,-3) berada di sana.", "Titik (1, minus 3) berada di sana."),
        ("Kurva x → ∞ dan x ⇒ y.", "Kurva x menuju tak hingga dan x maka y."),
        ("Syarat x ≤ 5 dan y ≥ 2, z ≠ 0.", "Syarat x kurang dari atau sama dengan 5 dan y lebih dari atau sama dengan 2, z tidak sama dengan 0."),
        ("Nilai 10⁻² dan x⁴.", "Nilai 10 pangkat minus dua dan x pangkat empat."),
    ],
)
def test_kasus_ambigu_dari_tinjauan_tidak_salah_ganti(text, expected):
    assert speakable(text) == expected


@pytest.mark.parametrize("text", ["Pangkat x^{1/2} akar.", "Pangkat x^2y dan 2^3x.", "Pangkat 2^{n} dan x^{1,5}."])
def test_pangkat_yang_bukan_angka_murni_dibiarkan_dan_ditandai(text):
    assert module.description_issues(speakable(text))
    assert "pangkat" not in speakable(text).replace("Pangkat", "")


def test_pangkat_angka_murni_sebelum_koma_dan_titik_diubah():
    assert speakable("Grafik x^2, lalu y^3.") == "Grafik x pangkat dua, lalu y pangkat tiga."


def test_garis_miring_tersisa_ditandai():
    assert module.description_issues("Rasio (x+1)/(x-1) ada.")
    assert module.description_issues("Ada 2 1/2 buah.")


def test_penanda_huruf_strip_angka_untuk_notasi_yang_dibiarkan_mentah():
    assert module.description_issues(speakable("Fungsi invers f-1 ada."))
    assert module.description_issues("Nilai x-1 tetap.")
    assert not module.description_issues("Kelas 10-19 berisi data.")

