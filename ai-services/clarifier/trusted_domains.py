from __future__ import annotations

import re
from urllib.parse import urlparse

# Tier 1 -- akademik/pemerintah, dicek lewat pattern (bukan whitelist domain persis karena
# mencakup banyak subdomain universitas/pemerintah yang tidak mungkin didaftar satu-satu).
TIER1_PATTERNS = [
    re.compile(r"(^|\.)[\w-]+\.edu$"),
    re.compile(r"(^|\.)[\w-]+\.edu\.\w{2,3}$"),   
    re.compile(r"(^|\.)[\w-]+\.ac\.id$"),        
    re.compile(r"(^|\.)[\w-]+\.gov$"),
    re.compile(r"(^|\.)[\w-]+\.go\.id$"),        
    re.compile(r"^arxiv\.org$"),
    re.compile(r"(^|\.)ncbi\.nlm\.nih\.gov$"),
]

# Tier 2 -- katalog OER yang sudah dikurasi manual, whitelist eksplisit (bukan pattern).
TIER2_DOMAINS = {
    "openstax.org",
    "khanacademy.org",
    "oercommons.org",
    "ocw.mit.edu",
    "rumahbelajar.kemdikbud.go.id",
    "belajar.id",
}

# Tier 3 = catch-all -- domain apapun yang tidak cocok tier 1/2 (Wikipedia, blog, situs edukasi
# umum seperti Zenius/RuangGuru/dst).
def domain_of(url: str) -> str:
    return (urlparse(url).netloc or url).lower().removeprefix("www.")


def trust_tier(url: str) -> int:
    """Balikkan 1 (akademik/pemerintah), 2 (OER kurasi), atau 3 (catch-all -- semua domain lain,
    termasuk Wikipedia/blog). Tidak pernah None -- tidak ada lagi domain yang ditolak/dibuang."""
    domain = domain_of(url)
    if any(pattern.search(domain) for pattern in TIER1_PATTERNS):
        return 1
    if domain in TIER2_DOMAINS:
        return 2
    return 3


def rank_results(results: list[dict], url_key: str = "url") -> list[dict]:
    """Tambahkan `trust_tier` ke tiap hasil (tidak ada yang dibuang), urutkan tier 1 duluan."""
    ranked = [{**result, "trust_tier": trust_tier(result[url_key])} for result in results]
    return sorted(ranked, key=lambda r: r["trust_tier"])
