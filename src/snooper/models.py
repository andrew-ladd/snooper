from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MediaKind(str, Enum):
    IMAGE = "image"
    GALLERY_IMAGE = "gallery_image"
    VIDEO = "video"
    EXTERNAL = "external"


@dataclass(frozen=True)
class MediaItem:
    url: str
    kind: MediaKind
    filename: Optional[str] = None
    caption: Optional[str] = None
    source: str = "reddit"


@dataclass(frozen=True)
class RedditPost:
    id: str
    subreddit: str
    title: str
    permalink: str
    over_18: bool
    is_video: bool
    media_items: tuple[MediaItem, ...]
    external_url: Optional[str] = None

