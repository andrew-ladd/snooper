from __future__ import annotations

from urllib.parse import urlparse, urlunparse


REDDIT_HOSTS = {
    "reddit.com",
    "www.reddit.com",
    "old.reddit.com",
    "new.reddit.com",
    "np.reddit.com",
    "m.reddit.com",
    "redd.it",
}


def is_reddit_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host in REDDIT_HOSTS


def normalize_reddit_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme:
        parsed = urlparse(f"https://{url}")

    host = parsed.netloc.lower()
    if host not in REDDIT_HOSTS:
        raise ValueError(f"not a supported Reddit URL: {url}")

    path = parsed.path.rstrip("/")
    if not path:
        raise ValueError(f"Reddit URL has no post path: {url}")

    return urlunparse(("https", host, f"{path}/", "", "", ""))


def reddit_json_url(url: str) -> str:
    normalized = normalize_reddit_url(url)
    return normalized.rstrip("/") + ".json"

