from pathlib import Path

from snooper.filenames import media_filename, post_directory, slugify


def test_slugify_removes_unsafe_characters():
    assert slugify("Leo: Carlsson / stunning move!") == "Leo-Carlsson-stunning-move"


def test_post_directory_uses_subreddit_id_and_title():
    assert post_directory(Path("downloads"), "nhl", "abc123", "Nice goal") == Path(
        "downloads/nhl-abc123-Nice-goal"
    )


def test_media_filename_preserves_supported_extension():
    assert media_filename("Nice goal", 2, "https://i.redd.it/x.webp?width=100") == "002-Nice-goal.webp"

