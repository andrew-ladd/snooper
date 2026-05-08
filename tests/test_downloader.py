import subprocess
from pathlib import Path

from snooper import downloader
from snooper.models import MediaItem, MediaKind, RedditPost


def test_dry_run_reddit_video_does_not_require_ffmpeg_or_yt_dlp(monkeypatch):
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

    monkeypatch.setattr(
        downloader,
        "_ensure_yt_dlp",
        lambda: (_ for _ in ()).throw(AssertionError("yt-dlp should not be required")),
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


def test_reddit_video_streams_use_best_video_and_audio(monkeypatch):
    manifest = b"""
    <MPD>
      <Period>
        <AdaptationSet mimeType="video/mp4">
          <Representation bandwidth="1000" height="480"><BaseURL>DASH_480.mp4</BaseURL></Representation>
          <Representation bandwidth="2000" height="720"><BaseURL>DASH_720.mp4</BaseURL></Representation>
        </AdaptationSet>
        <AdaptationSet mimeType="audio/mp4">
          <Representation bandwidth="64000"><BaseURL>DASH_AUDIO_64.mp4</BaseURL></Representation>
          <Representation bandwidth="128000"><BaseURL>DASH_AUDIO_128.mp4</BaseURL></Representation>
        </AdaptationSet>
      </Period>
    </MPD>
    """

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return manifest

    monkeypatch.setattr(downloader.urllib.request, "urlopen", lambda *args, **kwargs: Response())

    video_url, audio_url = downloader._reddit_video_streams("https://v.redd.it/abc123/DASH_480.mp4?source=fallback")

    assert video_url == "https://v.redd.it/abc123/DASH_720.mp4"
    assert audio_url == "https://v.redd.it/abc123/DASH_AUDIO_128.mp4"


def test_ensure_yt_dlp_installs_missing_dependency(monkeypatch):
    imports = []
    commands = []

    def fake_import_module(name):
        imports.append(name)
        if len(imports) == 1:
            raise ImportError(name)
        return object()

    def fake_run(command, check):
        commands.append((command, check))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(downloader.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(downloader.subprocess, "run", fake_run)
    monkeypatch.setattr(downloader.sys, "executable", "/venv/bin/python")

    downloader._ensure_yt_dlp()

    assert imports == ["yt_dlp", "yt_dlp"]
    assert commands == [(["/venv/bin/python", "-m", "pip", "install", "yt-dlp>=2025.1.0"], True)]
