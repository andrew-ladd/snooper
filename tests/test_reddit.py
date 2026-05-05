from snooper.models import MediaKind
from snooper.reddit import parse_post_payload
from snooper.urls import normalize_reddit_url, reddit_json_url


def payload(post):
    return [{"data": {"children": [{"data": post}]}}]


def test_normalizes_short_link_to_json_url():
    assert reddit_json_url("https://redd.it/abc123") == "https://redd.it/abc123.json"


def test_rejects_non_reddit_urls():
    try:
        normalize_reddit_url("https://example.com/post")
    except ValueError as exc:
        assert "not a supported Reddit URL" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_extracts_gallery_in_order_with_captions():
    post = parse_post_payload(
        payload(
            {
                "id": "abc123",
                "subreddit": "pics",
                "title": "Gallery",
                "permalink": "/r/pics/comments/abc123/gallery/",
                "gallery_data": {
                    "items": [
                        {"media_id": "one", "caption": "first"},
                        {"media_id": "two", "caption": "second"},
                    ]
                },
                "media_metadata": {
                    "one": {"m": "image/jpg", "s": {"u": "https://preview.redd.it/one.jpg?x=1&amp;y=2"}},
                    "two": {"m": "image/png", "s": {"u": "https://preview.redd.it/two.png"}},
                },
            }
        )
    )

    assert [item.url for item in post.media_items] == [
        "https://preview.redd.it/one.jpg?x=1&y=2",
        "https://preview.redd.it/two.png",
    ]
    assert [item.caption for item in post.media_items] == ["first", "second"]
    assert [item.kind for item in post.media_items] == [MediaKind.GALLERY_IMAGE, MediaKind.GALLERY_IMAGE]


def test_extracts_reddit_image():
    post = parse_post_payload(
        payload(
            {
                "id": "abc123",
                "subreddit": "pics",
                "title": "Image",
                "permalink": "/r/pics/comments/abc123/image/",
                "url_overridden_by_dest": "https://i.redd.it/example.webp",
            }
        )
    )

    assert len(post.media_items) == 1
    assert post.media_items[0].kind == MediaKind.IMAGE


def test_extracts_video_and_external_url():
    post = parse_post_payload(
        payload(
            {
                "id": "abc123",
                "subreddit": "videos",
                "title": "Video",
                "permalink": "/r/videos/comments/abc123/video/",
                "is_video": True,
                "secure_media": {
                    "reddit_video": {
                        "fallback_url": "https://v.redd.it/abc123/DASH_720.mp4?source=fallback"
                    }
                },
                "url_overridden_by_dest": "https://streamable.com/example",
            }
        )
    )

    assert [item.kind for item in post.media_items] == [MediaKind.VIDEO, MediaKind.EXTERNAL]

