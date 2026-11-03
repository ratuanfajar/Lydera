import threading

from common import llm, resilience


def test_breaker_sticky_setelah_trip_walau_ada_sukses_terlambat(systemic_error):
    breaker = resilience.Breaker(2)
    breaker.failure(systemic_error())
    breaker.failure(systemic_error())
    breaker.success()
    assert breaker.tripped


def test_breaker_tidak_trip_oleh_galat_non_sistemik():
    breaker = resilience.Breaker(2)
    for _ in range(5):
        breaker.failure(llm.ContentFilterError("ditolak"))
    assert not breaker.tripped


def test_breaker_aman_untuk_banyak_thread(systemic_error):
    breaker = resilience.Breaker(100)
    threads = [threading.Thread(target=lambda: [breaker.failure(systemic_error()) for _ in range(25)]) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert breaker.streak == 100 and breaker.tripped


def test_galat_kunci_azure_kosong_dianggap_sistemik():
    assert resilience.is_systemic(RuntimeError("AZURE_OPENAI_API_KEY dan AZURE_OPENAI_ENDPOINT belum diisi"))
    assert not resilience.is_systemic(RuntimeError("lain"))
    assert not resilience.is_systemic(llm.ContentFilterError("ditolak"))
