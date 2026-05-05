from pathlib import Path

from snooper import downloader
from snooper.models import MediaItem, MediaKind, RedditPost


def test_dry_run_video_does_not_require_ffmpeg(monkeypatch):
    post = RedditPost(
        id="abc123",
        subreddit="videos",
        title="Video",
        permalink="https://www.reddit.com/r/videos/comments/abc123/video/",
        over_18=False,
        is_video=True,
        media_items=(
            MediaItem(
                "https://v.redd.it/abc123/DASH_720.mp4",
                MediaKind.VIDEO,
                source="reddit_video",
            ),
        ),
    )

    monkeypatch.setattr(downloader, "_ensure_yt_dlp", lambda: None)
    monkeypatch.setattr(
        downloader,
        "_download_with_yt_dlp",
        lambda *args, **kwargs: [Path("~/Downloads/videos-abc123-Video/001-Video.mp4")],
    )
    monkeypatch.setattr(
        downloader.ffmpeg,
        "install_ffmpeg_if_possible",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("ffmpeg install should not run")
        ),
    )
    monkeypatch.setattr(
        downloader.ffmpeg,
        "ffmpeg_available",
        lambda: (_ for _ in ()).throw(AssertionError("ffmpeg check should not run")),
    )

    for install_ffmpeg in (True, False):
        paths = downloader.download_post(
            post,
            output_dir=Path("~/Downloads").expanduser(),
            dry_run=True,
            install_ffmpeg=install_ffmpeg,
        )

        assert paths[-1].name == "metadata.json"
