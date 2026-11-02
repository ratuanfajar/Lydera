from __future__ import annotations

from urllib.parse import urlparse

OER_HOSTS = frozenset({
    "murid.kemendikdasmen.go.id",
    "repositori.kemendikdasmen.go.id",
    "openstax.org",
    "www.khanacademy.org",
    "id.khanacademy.org",
    "en.khanacademy.org",
})


def host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def is_trusted(url: str) -> bool:
    try:
        return urlparse(url).scheme == "https" and host_of(url) in OER_HOSTS
    except ValueError:
        return False
