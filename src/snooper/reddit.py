from __future__ import annotations

import html
import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from .models import MediaItem, MediaKind, RedditPost
from .urls import reddit_json_url


USER_AGENT = "snooper/0.1 (+https://github.com/local/snooper)"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")


class RedditFetchError(RuntimeError):
    pass


def fetch_post(url: str, *, timeout: float = 30.0) -> RedditPost:
    request = urllib.request.Request(
        reddit_json_url(url),
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RedditFetchError(f"Reddit returned HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise RedditFetchError(f"failed to fetch Reddit post {url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RedditFetchError(f"Reddit returned invalid JSON for {url}") from exc

    return parse_post_payload(payload)


def parse_post_payload(payload: Any) -> RedditPost:
    try:
        listing = payload[0]["data"]["children"][0]["data"]
    except (TypeError, KeyError, IndexError) as exc:
        raise RedditFetchError("Reddit response did not contain a post") from exc

    media_items = tuple(_extract_media_items(listing))
    permalink = listing.get("permalink") or ""
    if permalink.startswith("/"):
        permalink = f"https://www.reddit.com{permalink}"

    return RedditPost(
        id=str(listing.get("id") or "unknown"),
        subreddit=str(listing.get("subreddit") or "reddit"),
        title=str(listing.get("title") or "reddit-post"),
        permalink=permalink,
        over_18=bool(listing.get("over_18")),
        is_video=bool(listing.get("is_video")),
        media_items=media_items,
        external_url=_external_url(listing),
    )


def _extract_media_items(post: dict[str, Any]) -> list[MediaItem]:
    items: list[MediaItem] = []
    items.extend(_gallery_items(post))
    items.extend(_image_items(post))
    items.extend(_reddit_video_items(post))

    external = _external_url(post)
    if external:
        items.append(MediaItem(external, MediaKind.EXTERNAL, source="external"))

    return _dedupe(items)


def _gallery_items(post: dict[str, Any]) -> list[MediaItem]:
    gallery_data = post.get("gallery_data") or {}
    media_metadata = post.get("media_metadata") or {}
    ordered = gallery_data.get("items") or []
    items: list[MediaItem] = []

    for index, gallery_item in enumerate(ordered, start=1):
        media_id = gallery_item.get("media_id")
        metadata = media_metadata.get(media_id) or {}
        url = _gallery_media_url(metadata)
        if not url:
            continue
        caption = gallery_item.get("caption") or metadata.get("caption")
        ext = _gallery_extension(metadata, url)
        items.append(
            MediaItem(
                url=url,
                kind=MediaKind.GALLERY_IMAGE,
                filename=f"{index:03d}-gallery{ext}",
                caption=caption,
            )
        )

    return items


def _gallery_media_url(metadata: dict[str, Any]) -> str | None:
    source = metadata.get("s") or {}
    url = source.get("u") or source.get("gif") or source.get("mp4")
    if not url:
        return None
    return html.unescape(str(url))


def _gallery_extension(metadata: dict[str, Any], url: str) -> str:
    mimetype = str(metadata.get("m") or "").lower()
    if "png" in mimetype:
        return ".png"
    if "webp" in mimetype:
        return ".webp"
    if "gif" in mimetype:
        return ".gif"
    parsed_ext = urlparse(url).path.rsplit(".", 1)
    if len(parsed_ext) == 2 and f".{parsed_ext[1].lower()}" in IMAGE_EXTENSIONS:
        return f".{parsed_ext[1].lower()}"
    return ".jpg"


def _image_items(post: dict[str, Any]) -> list[MediaItem]:
    url = post.get("url_overridden_by_dest") or post.get("url")
    if not isinstance(url, str):
        return []

    lower_path = urlparse(url).path.lower()
    if lower_path.endswith(IMAGE_EXTENSIONS):
        return [MediaItem(html.unescape(url), MediaKind.IMAGE)]
    return []


def _reddit_video_items(post: dict[str, Any]) -> list[MediaItem]:
    reddit_video = (
        ((post.get("secure_media") or {}).get("reddit_video"))
        or ((post.get("media") or {}).get("reddit_video"))
    )
    if not reddit_video:
        return []
    fallback_url = reddit_video.get("fallback_url")
    if fallback_url:
        return [MediaItem(html.unescape(str(fallback_url)), MediaKind.VIDEO, source="reddit_video")]
    return []


def _external_url(post: dict[str, Any]) -> str | None:
    url = post.get("url_overridden_by_dest") or post.get("url")
    if not isinstance(url, str):
        return None

    domain = urlparse(url).netloc.lower()
    if not domain:
        return None

    redditish_domains = {
        "i.redd.it",
        "v.redd.it",
        "preview.redd.it",
        "reddit.com",
        "www.reddit.com",
        "old.reddit.com",
    }
    if domain in redditish_domains:
        return None

    lower_path = urlparse(url).path.lower()
    if lower_path.endswith(IMAGE_EXTENSIONS):
        return None

    return html.unescape(url)


def _dedupe(items: list[MediaItem]) -> list[MediaItem]:
    seen: set[str] = set()
    deduped: list[MediaItem] = []
    for item in items:
        if item.url in seen:
            continue
        seen.add(item.url)
        deduped.append(item)
    return deduped

