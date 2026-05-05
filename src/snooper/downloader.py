from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from . import ffmpeg
from .filenames import media_filename, post_directory, unique_path
from .models import MediaItem, MediaKind, RedditPost


class DownloadError(RuntimeError):
    pass


def download_post(
    post: RedditPost,
    *,
    output_dir: Path,
    include_nsfw: bool = False,
    overwrite: bool = False,
    dry_run: bool = False,
    install_ffmpeg: bool = True,
    write_metadata: bool = True,
) -> list[Path]:
    if post.over_18 and not include_nsfw:
        raise DownloadError("post is marked NSFW; rerun with --include-nsfw to download it")

    if not post.media_items:
        return []

    if any(item.kind in {MediaKind.VIDEO, MediaKind.EXTERNAL} for item in post.media_items):
        _ensure_yt_dlp()
        if not dry_run and install_ffmpeg:
            attempt = ffmpeg.install_ffmpeg_if_possible(dry_run=dry_run)
            if not attempt.success and any(item.kind == MediaKind.VIDEO for item in post.media_items):
                raise DownloadError(attempt.message)
        elif (
            not dry_run
            and not ffmpeg.ffmpeg_available()
            and any(item.kind == MediaKind.VIDEO for item in post.media_items)
        ):
            raise DownloadError("ffmpeg is required for video downloads; install ffmpeg or omit --no-install-ffmpeg")

    target_dir = post_directory(output_dir, post.subreddit, post.id, post.title)
    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    downloaded: list[Path] = []
    for index, item in enumerate(post.media_items, start=1):
        if item.kind in {MediaKind.IMAGE, MediaKind.GALLERY_IMAGE}:
            downloaded.append(
                _download_direct(item, post, target_dir, index, overwrite=overwrite, dry_run=dry_run)
            )
        else:
            downloaded.extend(
                _download_with_yt_dlp(item, post, target_dir, index, overwrite=overwrite, dry_run=dry_run)
            )

    if write_metadata:
        metadata_path = target_dir / "metadata.json"
        if dry_run:
            downloaded.append(metadata_path)
        else:
            metadata_path.write_text(_metadata_json(post), encoding="utf-8")
            downloaded.append(metadata_path)

    return downloaded


def _download_direct(
    item: MediaItem,
    post: RedditPost,
    target_dir: Path,
    index: int,
    *,
    overwrite: bool,
    dry_run: bool,
) -> Path:
    filename = item.filename or media_filename(post.title, index, item.url, default_ext=".jpg")
    destination = unique_path(target_dir / filename, overwrite=overwrite)
    if dry_run:
        return destination
    if destination.exists() and not overwrite:
        return destination

    request = urllib.request.Request(item.url, headers={"User-Agent": "snooper/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            with destination.open("wb") as output:
                shutil.copyfileobj(response, output)
    except urllib.error.URLError as exc:
        raise DownloadError(f"failed to download {item.url}: {exc.reason}") from exc

    return destination


def _download_with_yt_dlp(
    item: MediaItem,
    post: RedditPost,
    target_dir: Path,
    index: int,
    *,
    overwrite: bool,
    dry_run: bool,
) -> list[Path]:
    from yt_dlp import YoutubeDL

    before = _directory_snapshot(target_dir)
    output_template = str(target_dir / f"{index:03d}-%(title).90B.%(ext)s")
    download_url = post.permalink if item.kind == MediaKind.VIDEO and item.source == "reddit_video" else item.url
    options = {
        "outtmpl": output_template,
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "overwrites": overwrite,
        "quiet": True,
        "no_warnings": True,
        "simulate": dry_run,
    }

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(download_url, download=not dry_run)

    if dry_run:
        ext = (info or {}).get("ext") or "media"
        title = (info or {}).get("title") or post.title
        return [target_dir / media_filename(title, index, item.url, default_ext=f".{ext}")]

    after = _directory_snapshot(target_dir)
    created = sorted(after - before)
    if created:
        return list(created)

    requested = Path(YoutubeDL(options).prepare_filename(info))
    return [requested]


def _directory_snapshot(directory: Path) -> set[Path]:
    if not directory.exists():
        return set()
    return {path for path in directory.iterdir() if path.is_file()}


def _ensure_yt_dlp() -> None:
    try:
        import yt_dlp  # noqa: F401
    except ImportError as exc:
        raise DownloadError("yt-dlp is required; install snooper with `python3 -m pip install -e .`") from exc


def _metadata_json(post: RedditPost) -> str:
    metadata = asdict(post)
    return json.dumps(metadata, indent=2, sort_keys=True) + "\n"


def describe_media(items: Iterable[MediaItem]) -> list[str]:
    return [f"{item.kind.value}: {item.url}" for item in items]
