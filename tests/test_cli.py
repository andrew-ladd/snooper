from pathlib import Path

from snooper import cli
from snooper.models import MediaItem, MediaKind, RedditPost


def test_default_output_directory_expands_home(monkeypatch):
    post = RedditPost(
        id="abc123",
        subreddit="pics",
        title="Image",
        permalink="https://www.reddit.com/r/pics/comments/abc123/image/",
        over_18=False,
        is_video=False,
        media_items=(MediaItem("https://i.redd.it/example.jpg", MediaKind.IMAGE),),
    )
    captured = {}

    monkeypatch.setattr(cli, "fetch_post", lambda url: post)

    def fake_download_post(post, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(cli, "download_post", fake_download_post)

    assert cli.main(["https://redd.it/abc123"]) == 0
    assert captured["output_dir"] == Path.home() / "Downloads"
