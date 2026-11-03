import json
from types import SimpleNamespace

import httpx
import pytest

from clarifier import agent, citations, config, external_tools, tools, trusted_domains

REAL_URL = "https://murid.kemendikdasmen.go.id/sumber-belajar/sub-unit/99f1deaf-bc6c-4d6e-81a8-f450d8130c85/materi/lingkaran-dan-busur-lingkaran-48573eae-0e71-4cff-b323-5941ecacafe1"
TYPO_URL = REAL_URL.replace("bc6c", "cb6c")
OTHER_URL = "https://murid.kemendikdasmen.go.id/sumber-belajar/sub-unit/302e5cd2-7ccd-454b-9093-2b94b6b54568/materi/penjelasan-elemen-dan-teorema-lingkaran"

RAW_RESULTS = [
    {"url": "https://murid.kemendikdasmen.go.id/a", "title": "A", "snippet": "isi a", "score": 0.91},
    {"url": "https://www.khanacademy.org/b", "title": "B", "snippet": "isi b", "score": 0.7},
    {"url": "https://www.khanacademy.org/c", "title": "C", "snippet": "isi c", "score": 0.69},
    {"url": "https://zh.khanacademy.org/d", "title": "D", "snippet": "isi d", "score": 0.95},
    {"url": "https://blog.example.com/e", "title": "E", "snippet": "isi e", "score": 0.99},
]


@pytest.fixture
def search_config(monkeypatch):
    monkeypatch.setattr(config, "SEARCH_API_KEY", "kunci")
    monkeypatch.setattr(config, "OER_MIN_SCORE", 0.7)


@pytest.fixture
def store():
    return {
        REAL_URL: "Lingkaran Dan Busur Lingkaran Pada materi ini kamu akan mempelajari hubungan antara sudut pusat dan sudut keliling",
        OTHER_URL: "teks lain",
        "85": "teks modul",
    }


def stub_fetch(monkeypatch, fetch):
    monkeypatch.setattr(external_tools, "fetch_results", fetch)


def stub_post(monkeypatch, payload, sent=None):
    def post(*args, **kwargs):
        if sent is not None:
            sent.update(kwargs)
        return httpx.Response(200, json=payload, request=httpx.Request("POST", "https://api.tavily.com/search"))

    monkeypatch.setattr(external_tools.httpx, "post", post)


def status_error(query):
    request = httpx.Request("POST", "https://api.tavily.com/search?appid=RAHASIA")
    response = httpx.Response(401, request=request)
    raise httpx.HTTPStatusError("gagal https://api.tavily.com/search?appid=RAHASIA", request=request, response=response)


def connect_error(query):
    raise httpx.ConnectError("tidak bisa tersambung ke https://api.tavily.com?key=RAHASIA")


@pytest.mark.parametrize(
    "url",
    [
        "https://murid.kemendikdasmen.go.id/sumber-belajar/x",
        "https://www.khanacademy.org/math/geometry",
        "https://id.khanacademy.org/math",
        "https://openstax.org/books/algebra",
        "https://OpenStax.org:443/x",
        "https://repositori.kemendikdasmen.go.id/10532/1/Modul.pdf",
    ],
)
def test_is_trusted_menerima_host_kurasi(url):
    assert trusted_domains.is_trusted(url)


def test_fetch_results_membersihkan_karakter_font_simbol_dari_pdf(monkeypatch, search_config):
    payload = {"results": [{"url": "https://repositori.kemendikdasmen.go.id/1/a.pdf", "title": "T", "content": "fungsi\uf0b7  komposisi \uf0b4 \xa0g", "score": 0.8}]}
    stub_post(monkeypatch, payload)
    assert external_tools.fetch_results("komposisi")[0]["snippet"] == "fungsi komposisi g"


def test_fetch_results_mengirim_daftar_host_dan_batas_hasil(monkeypatch, search_config):
    sent = {}
    stub_post(monkeypatch, {"results": []}, sent)
    external_tools.fetch_results("komposisi")
    assert sent["json"]["include_domains"] == sorted(trusted_domains.OER_HOSTS)
    assert sent["json"]["max_results"] == 5


def test_fetch_results_menerima_konten_null(monkeypatch, search_config):
    stub_post(monkeypatch, {"results": [{"url": "https://openstax.org/a", "title": "T", "content": None, "score": 0.9}]})
    assert external_tools.fetch_results("x")[0]["snippet"] == ""


def test_search_oer_membuang_hasil_dengan_cuplikan_kosong(monkeypatch, search_config):
    stub_fetch(monkeypatch, lambda query: [{"url": "https://openstax.org/a", "title": "T", "snippet": "", "score": 0.9}])
    assert external_tools.search_oer("x")["results"] == []


def test_search_oer_json_bukan_objek_dilaporkan_gagal(monkeypatch, search_config):
    stub_post(monkeypatch, ["bukan objek"])
    result = external_tools.search_oer("x")
    assert result["available"] is False
    assert result["note"] == "Search API error: AttributeError"


def test_oer_hosts_persis_enam_host():
    assert trusted_domains.OER_HOSTS == {
        "murid.kemendikdasmen.go.id", "repositori.kemendikdasmen.go.id", "openstax.org",
        "www.khanacademy.org", "id.khanacademy.org", "en.khanacademy.org",
    }


@pytest.mark.parametrize("url", ["https://[x", "http://", ""])
def test_is_trusted_url_rusak_tidak_melempar(url):
    assert trusted_domains.is_trusted(url) is False


def test_dispatch_search_oer_menggabungkan_cuplikan_url_yang_sama(monkeypatch, search_config):
    calls = iter([
        [{"url": "https://openstax.org/a", "title": "T", "snippet": "kalimat pertama", "score": 0.9}],
        [{"url": "https://openstax.org/a", "title": "T", "snippet": "kalimat kedua", "score": 0.9}],
    ])
    stub_fetch(monkeypatch, lambda query: next(calls))
    outputs = {}
    call = SimpleNamespace(function=SimpleNamespace(name="search_oer", arguments='{"query": "x"}'))
    agent._dispatch(call, lambda q: [], outputs)
    agent._dispatch(call, lambda q: [], outputs)
    assert "kalimat pertama" in outputs["https://openstax.org/a"]
    assert "kalimat kedua" in outputs["https://openstax.org/a"]


def test_verify_citations_angka_dua_digit_ikut_diverifikasi():
    outputs = {"85": "Jarak total pada kecepatan 80 adalah 69 meter"}
    benar = {"source_type": "modul", "reference": "85", "evidence": "jarak total pada kecepatan 80 adalah 69 meter"}
    salah = {"source_type": "modul", "reference": "85", "evidence": "jarak total pada kecepatan 80 adalah 96 meter"}
    assert citations.verify_citations([benar, salah], outputs)[0]["verified"] is True
    assert citations.verify_citations([salah], outputs)[0]["verified"] is False


@pytest.mark.parametrize(
    "url",
    [
        "https://zh.khanacademy.org/math",
        "https://cs.khanacademy.org/x",
        "https://khanacademy.org/x",
        "https://assets.openstax.org/x.pdf",
        "https://sma.kemendikdasmen.go.id/a.pdf",
        "https://unbounded-uploads.s3.amazonaws.com/x",
        "https://en.wikipedia.org/wiki/Circle",
        "https://evil.com/?u=www.khanacademy.org",
        "https://www.khanacademy.org.evil.com/x",
        "http://www.khanacademy.org/math",
        "bukan-url",
        "",
    ],
)
def test_is_trusted_menolak_host_di_luar_daftar(url):
    assert not trusted_domains.is_trusted(url)


def test_search_oer_menyaring_host_dan_skor(monkeypatch, search_config):
    stub_fetch(monkeypatch, lambda query: RAW_RESULTS)
    result = external_tools.search_oer("sudut keliling")
    assert result["available"] is True
    assert [r["title"] for r in result["results"]] == ["A", "B"]


def test_search_oer_memberi_catatan_bila_semua_hasil_tersaring(monkeypatch, search_config):
    stub_fetch(monkeypatch, lambda query: [r for r in RAW_RESULTS if r["score"] < 0.7])
    expected = {"available": True, "results": [], "note": external_tools.NO_TRUSTED_SOURCE_NOTE}
    assert external_tools.search_oer("apa saja") == expected


def test_search_oer_hasil_kosong_dari_api_menghasilkan_daftar_kosong(monkeypatch, search_config):
    stub_fetch(monkeypatch, lambda query: [])
    assert external_tools.search_oer("x")["results"] == []


def test_search_oer_error_status_tidak_membocorkan_url(monkeypatch, search_config):
    stub_fetch(monkeypatch, status_error)
    failed = external_tools.search_oer("x")
    assert failed == {"available": False, "results": [], "note": "Search API error 401"}
    assert "RAHASIA" not in json.dumps(failed)


def test_search_oer_error_koneksi_hanya_menyebut_nama_error(monkeypatch, search_config):
    stub_fetch(monkeypatch, connect_error)
    failed = external_tools.search_oer("x")
    assert failed["note"] == "Search API error: ConnectError"
    assert "RAHASIA" not in json.dumps(failed)


def test_search_oer_tanpa_kunci_tidak_tersedia(monkeypatch):
    monkeypatch.setattr(config, "SEARCH_API_KEY", "")
    assert external_tools.search_oer("x")["available"] is False


def test_tools_schema_berisi_empat_tool_berurutan():
    assert [t["function"]["name"] for t in tools.TOOLS_SCHEMA] == ["search_module", "search_oer", "request_practice", "compose_answer"]


def test_compose_answer_hanya_menerima_sumber_modul_dan_oer():
    properties = tools.TOOLS_SCHEMA[-1]["function"]["parameters"]["properties"]
    assert properties["sources"]["items"]["properties"]["source_type"]["enum"] == ["modul", "oer"]


@pytest.mark.parametrize("removed", ["query_wolfram_alpha", "search_academic_web"])
def test_dispatch_menolak_tool_yang_sudah_dihapus(removed):
    call = SimpleNamespace(function=SimpleNamespace(name=removed, arguments="{}"))
    assert json.loads(agent._dispatch(call, lambda q: [], {})) == {"error": f"tool tidak dikenal: {removed}"}


def test_system_prompt_tidak_menyebut_tool_yang_sudah_dihapus():
    assert "wolfram" not in agent.SYSTEM_PROMPT.lower()
    assert "search_academic_web" not in agent.SYSTEM_PROMPT
    assert "trust_tier" not in agent.SYSTEM_PROMPT


def verify(store, **citation):
    base = {"source_type": "modul", "label": "l", "justification": "j"}
    return citations.verify_citations([{**base, **citation}], store)[0]


def test_verify_citations_menandai_rujukan_yang_tidak_ada_di_hasil_tool():
    outputs = {"85": "Sudut pusat dua kali sudut keliling", "https://www.khanacademy.org/b": "Judul isi inscribed angle"}
    cited = citations.verify_citations(
        [
            {"source_type": "modul", "label": "m", "reference": "85", "evidence": "Sudut pusat dua kali sudut keliling", "justification": "j"},
            {"source_type": "oer", "label": "o", "reference": "https://www.khanacademy.org/b", "evidence": "inscribed angle", "justification": "j"},
            {"source_type": "oer", "label": "o2", "reference": "https://www.khanacademy.org/dikarang", "evidence": "inscribed angle", "justification": "j"},
        ],
        outputs,
    )
    assert [c["verified"] for c in cited] == [True, True, False]
    assert all("trust_tier" not in c for c in cited)


def test_verify_citations_memperbaiki_url_oer_yang_salah_ketik(store):
    result = verify(store, source_type="oer", reference=TYPO_URL, evidence="mempelajari hubungan antara sudut pusat dan sudut keliling")
    assert result["verified"] is True
    assert result["reference"] == REAL_URL


def test_verify_citations_url_oer_tak_dikenal_tidak_terverifikasi(store):
    unknown = "https://murid.kemendikdasmen.go.id/sumber-belajar/lain/sama-sekali"
    result = verify(store, source_type="oer", reference=unknown, evidence="mempelajari hubungan antara sudut pusat")
    assert result["verified"] is False
    assert result["reference"] == unknown


def test_verify_citations_url_oer_salah_ketik_dengan_kutipan_karangan_tidak_diperbaiki(store):
    result = verify(store, source_type="oer", reference=TYPO_URL, evidence="kalimat karangan yang tidak ada di sumber sama sekali")
    assert result["verified"] is False
    assert result["reference"] == TYPO_URL


def test_verify_citations_url_oer_dengan_angka_tidak_dianggap_blok_modul(store):
    assert verify(store, source_type="oer", reference="https://x.org/85", evidence="teks modul")["verified"] is False


def test_verify_citations_modul_dengan_rujukan_berderau_tetap_terverifikasi(store):
    result = verify(store, reference="block_id 85", evidence="teks modul")
    assert result["verified"] is True
    assert result["reference"] == "block_id 85"


def test_verify_citations_oer_dengan_rujukan_angka_tidak_terverifikasi(store):
    result = verify(store, source_type="oer", reference="85", evidence="teks modul")
    assert result["verified"] is False
    assert result["reference"] == "85"


def test_verify_citations_modul_dengan_rujukan_url_tidak_terverifikasi(store):
    result = verify(store, reference=REAL_URL, evidence="mempelajari hubungan antara sudut pusat")
    assert result["verified"] is False


def test_system_prompt_memuat_aturan_data_dan_isian_kosong():
    prompt = agent.SYSTEM_PROMPT
    assert "DATA" in prompt
    assert "isian kosong" in prompt
