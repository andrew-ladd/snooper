from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

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

    if any(item.kind == MediaKind.VIDEO for item in post.media_items):
        if not dry_run and install_ffmpeg:
            attempt = ffmpeg.install_ffmpeg_if_possible(dry_run=dry_run)
            if not attempt.success:
                raise DownloadError(attempt.message)
        elif not dry_run and not ffmpeg.ffmpeg_available():
            raise DownloadError("ffmpeg is required for video downloads; install ffmpeg or omit --no-install-ffmpeg")

    if any(item.kind == MediaKind.EXTERNAL for item in post.media_items):
        _ensure_yt_dlp()

    target_dir = post_directory(output_dir, post.subreddit, post.id, post.title)
    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    downloaded: list[Path] = []
    for index, item in enumerate(post.media_items, start=1):
        if item.kind in {MediaKind.IMAGE, MediaKind.GALLERY_IMAGE}:
            downloaded.append(
                _download_direct(item, post, target_dir, index, overwrite=overwrite, dry_run=dry_run)
            )
        elif item.kind == MediaKind.VIDEO and item.source == "reddit_video":
            downloaded.append(
                _download_reddit_video(item, post, target_dir, index, overwrite=overwrite, dry_run=dry_run)
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


def _download_reddit_video(
    item: MediaItem,
    post: RedditPost,
    target_dir: Path,
    index: int,
    *,
    overwrite: bool,
    dry_run: bool,
) -> Path:
    filename = media_filename(post.title, index, item.url, default_ext=".mp4")
    destination = unique_path(target_dir / filename, overwrite=overwrite)
    if dry_run:
        return destination
    if destination.exists() and not overwrite:
        return destination

    video_url, audio_url = _reddit_video_streams(item.url)
    command = [
        "ffmpeg",
        "-y" if overwrite else "-n",
        "-loglevel",
        "error",
        "-i",
        video_url,
    ]
    if audio_url:
        command.extend(["-i", audio_url])
    command.extend(["-c", "copy", str(destination)])

    try:
        subprocess.run(command, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise DownloadError(f"failed to download Reddit video with ffmpeg: {exc}") from exc

    return destination


def _reddit_video_streams(fallback_url: str) -> tuple[str, str | None]:
    playlist_url = _reddit_video_playlist_url(fallback_url)
    try:
        request = urllib.request.Request(playlist_url, headers={"User-Agent": "snooper/0.1"})
        with urllib.request.urlopen(request, timeout=30) as response:
            manifest = response.read()
    except urllib.error.URLError:
        return fallback_url, None

    try:
        root = ET.fromstring(manifest)
    except ET.ParseError:
        return fallback_url, None

    video_url: str | None = None
    video_score = -1
    audio_url: str | None = None
    audio_score = -1

    for adaptation in root.findall(".//{*}AdaptationSet"):
        mime_type = str(adaptation.get("mimeType") or adaptation.get("contentType") or "").lower()
        for representation in adaptation.findall("{*}Representation"):
            stream_url = _representation_base_url(playlist_url, representation)
            if not stream_url:
                continue
            score = _representation_score(representation)
            representation_mime = str(representation.get("mimeType") or mime_type).lower()
            if "audio" in representation_mime or "audio" in mime_type:
                if score > audio_score:
                    audio_url = stream_url
                    audio_score = score
            elif "video" in representation_mime or "video" in mime_type:
                if score > video_score:
                    video_url = stream_url
                    video_score = score

    return video_url or fallback_url, audio_url


def _reddit_video_playlist_url(fallback_url: str) -> str:
    path = fallback_url.split("?", 1)[0]
    if "/" not in path:
        return fallback_url
    return f"{path.rsplit('/', 1)[0]}/DASHPlaylist.mpd"


def _representation_base_url(playlist_url: str, representation: ET.Element) -> str | None:
    base_url = representation.findtext("{*}BaseURL")
    if not base_url:
        return None
    return urljoin(playlist_url, base_url)


def _representation_score(representation: ET.Element) -> int:
    for key in ("height", "bandwidth"):
        value = representation.get(key)
        if value and value.isdigit():
            return int(value)
    return 0


def _directory_snapshot(directory: Path) -> set[Path]:
    if not directory.exists():
        return set()
    return {path for path in directory.iterdir() if path.is_file()}


def _ensure_yt_dlp() -> None:
    try:
        importlib.import_module("yt_dlp")
    except ImportError:
        _install_yt_dlp()
        try:
            importlib.import_module("yt_dlp")
        except ImportError as exc:
            raise DownloadError("yt-dlp was installed but could not be imported") from exc


def _install_yt_dlp() -> None:
    command = [sys.executable, "-m", "pip", "install", "yt-dlp>=2025.1.0"]
    try:
        subprocess.run(command, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise DownloadError(
            "yt-dlp is required for external media links, but automatic installation failed. "
            f"Install it manually with `{' '.join(command)}`."
        ) from exc


def _metadata_json(post: RedditPost) -> str:
    metadata = asdict(post)
    return json.dumps(metadata, indent=2, sort_keys=True) + "\n"


def describe_media(items: Iterable[MediaItem]) -> list[str]:
    return [f"{item.kind.value}: {item.url}" for item in items]
