from __future__ import annotations

import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


_UNSAFE = re.compile(r"[^A-Za-z0-9._ -]+")
_WHITESPACE = re.compile(r"\s+")


def slugify(value: str, *, fallback: str = "reddit-post", max_length: int = 90) -> str:
    value = _UNSAFE.sub("", value).strip()
    value = _WHITESPACE.sub("-", value)
    value = value.strip(".-_")
    if not value:
        value = fallback
    return value[:max_length].rstrip(".-_") or fallback


def extension_from_url(url: str, default: str = ".bin") -> str:
    path = urlparse(url).path
    suffix = Path(path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".m4v", ".mov"}:
        return suffix
    return default


def unique_path(path: Path, *, overwrite: bool = False) -> Path:
    if overwrite or not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def post_directory(base: Path, subreddit: str, post_id: str, title: str) -> Path:
    return base / slugify(f"{subreddit}-{post_id}-{title}", fallback=post_id)


def media_filename(
    post_title: str,
    index: int,
    url: str,
    *,
    prefix: Optional[str] = None,
    default_ext: str = ".bin",
) -> str:
    ext = extension_from_url(url, default=default_ext)
    stem = slugify(prefix or post_title)
    return f"{index:03d}-{stem}{ext}"

