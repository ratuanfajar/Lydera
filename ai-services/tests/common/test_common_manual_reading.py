import pytest

from common.speakable import manual_reading_issues


def test_teks_bacaan_biasa_tidak_bermasalah():
    assert manual_reading_issues("Kurva naik dari kiri bawah ke kanan atas dan memotong sumbu y di titik tiga.") == []


@pytest.mark.parametrize("text", ["", "   ", None])
def test_teks_kosong_ditolak(text):
    assert manual_reading_issues(text)


@pytest.mark.parametrize("text", ["Nilai **tebal** dan kurva", "Kolom | nilai", "# Judul\nisi", "kode `x`"])
def test_markdown_ditolak(text):
    assert any("markdown" in issue for issue in manual_reading_issues(text))


@pytest.mark.parametrize("text", ["x^2 sama dengan empat", "f(x) sama dengan dua", "a = b", "titik $A$"])
def test_notasi_mentah_ditolak(text):
    assert any("mentah" in issue for issue in manual_reading_issues(text))


@pytest.mark.parametrize("text", ["Harga Rp5.000, panjang 3,5 meter dan 1.000 orang.", "Kurva naik (lalu turun) di titik tiga!"])
def test_desimal_ribuan_dan_tanda_baca_biasa_lolos(text):
    assert manual_reading_issues(text) == []


@pytest.mark.parametrize("text", ["6 ÷ 2", "himpunan A ∪ B", "luas 5²", "3 \\times 4", "laju 60 km/jam", "titik A-5", "a < b", "teks *miring*", "<b>tebal</b>", "[tautan](x)"])
def test_simbol_bermasalah_untuk_tts_ditolak(text):
    assert manual_reading_issues(text)


def test_pesan_menyebut_potongan_yang_bermasalah():
    assert any("'÷'" in issue for issue in manual_reading_issues("enam ÷ dua"))


def test_plain_text_issues_mengabaikan_rumus_dan_memeriksa_di_luarnya():
    from common.math_text import plain_text_issues

    assert plain_text_issues(["Nilai $x^{2} = 4$ untuk dua", "", None]) == []
    assert plain_text_issues(["Nilai x = 4 untuk $y$"])
