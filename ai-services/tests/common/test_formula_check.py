import pytest

from common import formula_check as check


@pytest.mark.parametrize(
    "latex, spoken",
    [
        (r"\sqrt{16}", "akar kuadrat dari enam belas"),
        (r"\sqrt{a^{2} + b^{2}}", "akar kuadrat dari a pangkat dua ditambah b pangkat dua selesai akar"),
        (r"\sqrt{2 5}", "akar kuadrat dari dua puluh lima"),
        (r"\frac{a + b}{c}", "pecahan dengan pembilang a ditambah b dan penyebut c selesai pecahan"),
        (r"\frac{3}{4}", "tiga per empat"),
        (r"\frac{1 0}{2 5}", "sepuluh per dua puluh lima"),
        (r"\dfrac{3}{4}", "tiga per empat"),
        (r"\frac{\pi}{2}", "pi per dua"),
        (r"\frac{\Delta y}{\Delta x}", "delta y per delta x"),
        ("x^{2}", "x pangkat dua"),
        ("2^{3x + 1}", "dua pangkat tiga x ditambah satu selesai pangkat"),
        (r"2^{\pi}", "dua pangkat pi"),
        ("f(g(4))", "f dari g dari empat"),
        ("f(-x)", "f dari negatif x"),
        ("2(x)", "dua buka kurung x tutup kurung"),
        ("p(x,y)", "p buka kurung x koma y tutup kurung"),
    ],
)
def test_spoken_issues_kosong_untuk_bacaan_benar(latex, spoken):
    assert check.spoken_issues(latex, spoken) == []


@pytest.mark.parametrize(
    "latex, spoken",
    [
        (r"\sqrt{a^{2} + b^{2}}", "akar kuadrat dari a pangkat dua ditambah b pangkat dua"),
        (r"\frac{3}{4}", "tiga per empat selesai pecahan selesai pecahan"),
        ("x = 3", "x sama dengan tiga selesai pecahan"),
        ("x = 3", "x sama dengan 3"),
        ("f(g(4))", "f buka kurung g buka kurung empat tutup kurung tutup kurung"),
        ("f(x)", "f buka kurung x tutup kurung"),
        ("(a+b)", "buka kurung a ditambah b"),
    ],
)
def test_spoken_issues_melaporkan_bacaan_salah(latex, spoken):
    assert check.spoken_issues(latex, spoken)


@pytest.mark.parametrize(
    "latex",
    [
        "abc + 12 + 3x - 4y + 5z + 6w + 7v + 8u + 9t + 10s + 11r + 12q + 13p",
        "(((a+(b+(c+d)))))",
    ],
)
def test_complexity_issues_kosong_untuk_rumus_datar_atau_kurung_biasa(latex):
    assert check.complexity_issues(latex) == []


def test_complexity_issues_melaporkan_pecahan_bersusun_dalam():
    deep = r"\frac{\frac{\frac{\frac{1}{2}}{3}}{4}}{5}"
    assert check.complexity_issues(deep)


@pytest.mark.parametrize(
    "latex, spoken",
    [
        ("P(a, b)", "titik P dengan koordinat a dan b"),
        ("O(0, 0)", "titik O dengan koordinat nol dan nol"),
        ("Q(1, 2, 3)", "titik Q dengan koordinat satu, dua, dan tiga"),
        ("P(A)", "P dari A"),
        ("f(x, y)", "f dari x dan y"),
        ("a + b", "a ditambah b"),
    ],
)
def test_spoken_issues_titik_berkoordinat_benar(latex, spoken):
    assert check.spoken_issues(latex, spoken) == []


@pytest.mark.parametrize(
    "latex, spoken",
    [
        ("P(a, b)", "P dari buka kurung a koma b tutup kurung"),
        ("A(2, 5)", "A buka kurung dua koma lima tutup kurung"),
        ("C(x_1, y_1)", "C dari x sub satu dan y sub satu"),
    ],
)
def test_spoken_issues_titik_bernama_tanpa_koordinat_ditandai(latex, spoken):
    assert any("koordinat" in issue for issue in check.spoken_issues(latex, spoken))


@pytest.mark.parametrize("command, spoken", [("pm", "plus atau minus"), ("mp", "minus atau plus")])
def test_spoken_issues_plus_minus_benar(command, spoken):
    latex = "a " + chr(92) + command + " b"
    assert check.spoken_issues(latex, "a " + spoken + " b") == []


@pytest.mark.parametrize("command, spoken", [("pm", "plus minus"), ("pm", "tambah kurang"), ("mp", "minus plus")])
def test_spoken_issues_plus_minus_salah_ditandai(command, spoken):
    latex = "a " + chr(92) + command + " b"
    assert any("plus" in issue for issue in check.spoken_issues(latex, "a " + spoken + " b"))


def test_has_named_point_tahan_spasi_panjang():
    import time

    started = time.perf_counter()
    check.has_named_point("A(" + " " * 300 + "," + " " * 300)
    assert time.perf_counter() - started < 1


@pytest.mark.parametrize(
    "latex, expected",
    [("P(a, b)", True), (r"C(5, 2) = 10", False), (r"X \sim B(10, 0.5)", False), (r"\{ (x, y) \mid y > 0 \}", False), ("A'(4, 6)", True)],
)
def test_has_named_point_membedakan_titik_dan_notasi_bernilai(latex, expected):
    assert check.has_named_point(latex) is expected


@pytest.mark.parametrize("latex", [r"a \pm b", "a ± b"])
def test_plus_minus_wajib_dibaca_plus_atau_minus(latex):
    assert check.spoken_issues(latex, "a tambah kurang b")
    assert not check.spoken_issues(latex, "a plus atau minus b")


@pytest.mark.parametrize(
    "latex, word",
    [
        (r"\vec{a} + \vec{b}", "vektor"),
        (r"\overrightarrow{AB}", "vektor"),
        (r"\int x \, dx", "integral"),
        (r"\sum x_{i}", "jumlah"),
        (r"\lim_{x \to 0} f(x)", "limit"),
        (r"\begin{pmatrix} 1 & 2 \ 3 & 4 \end{pmatrix}", "matriks"),
    ],
)
def test_notasi_wajib_memuat_kata_kunci(latex, word):
    assert any(f"'{word}'" in issue for issue in check.spoken_issues(latex, "a b c"))
    assert not any(f"'{word}'" in issue for issue in check.spoken_issues(latex, f"{word} a b c"))


@pytest.mark.parametrize("latex", [r"\int_{0}^{1} x \, dx", r"\sum_{i=1}^{n} x_{i}", r"\int\limits_{0}^{1} x"])
def test_integral_dan_jumlah_dengan_batas_juga_wajib_memuat_kata_kunci(latex):
    issues = check.spoken_issues(latex, "a b c")
    assert any("integral" in issue or "jumlah" in issue for issue in issues)


@pytest.mark.parametrize("latex", [r"\iint f", r"\intercal"])
def test_perintah_mirip_tidak_dipaksa_memuat_kata_kunci(latex):
    assert not any("integral" in issue for issue in check.spoken_issues(latex, "a b c"))


def test_overrightarrow_menerima_sinar_atau_vektor():
    assert not any("vektor" in issue for issue in check.spoken_issues(r"\overrightarrow{AB}", "sinar A B"))
    assert any("vektor" in issue for issue in check.spoken_issues(r"\vec{a}", "sinar a"))
