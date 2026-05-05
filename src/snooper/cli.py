from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .downloader import DownloadError, describe_media, download_post
from .reddit import RedditFetchError, fetch_post


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="snooper",
        description="Download media associated with Reddit posts.",
    )
    parser.add_argument(
        "urls",
        nargs="+",
        help="Reddit post URLs. Use '-' to read URLs from stdin.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="~/Downloads",
        type=Path,
        help="Output directory. Defaults to ~/Downloads.",
    )
    parser.add_argument(
        "--include-nsfw",
        action="store_true",
        help="Allow downloads from posts marked NSFW.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files instead of creating unique names.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded without writing files.",
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Do not write metadata.json beside downloaded files.",
    )
    parser.add_argument(
        "--no-install-ffmpeg",
        action="store_true",
        help="Do not attempt to install ffmpeg if it is missing.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Only print warnings and errors.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    urls = _expand_urls(args.urls)
    if not urls:
        print("warning: no URLs provided", file=sys.stderr)
        return 0

    failures = 0
    for url in urls:
        try:
            post = fetch_post(url)
            if not post.media_items:
                print(f"warning: no media found for {url}", file=sys.stderr)
                continue

            if args.dry_run and not args.quiet:
                print(f"{post.subreddit}/{post.id}: {post.title}")
                for line in describe_media(post.media_items):
                    print(f"  {line}")

            paths = download_post(
                post,
                output_dir=args.output.expanduser(),
                include_nsfw=args.include_nsfw,
                overwrite=args.overwrite,
                dry_run=args.dry_run,
                install_ffmpeg=not args.no_install_ffmpeg,
                write_metadata=not args.no_metadata,
            )
        except (DownloadError, RedditFetchError, ValueError) as exc:
            failures += 1
            print(f"error: {url}: {exc}", file=sys.stderr)
            continue

        if not args.quiet:
            verb = "would write" if args.dry_run else "wrote"
            for path in paths:
                print(f"{verb}: {path}")

    return 1 if failures else 0


def _expand_urls(urls: list[str]) -> list[str]:
    expanded: list[str] = []
    for url in urls:
        if url == "-":
            expanded.extend(line.strip() for line in sys.stdin if line.strip())
        else:
            expanded.append(url)
    return expanded


if __name__ == "__main__":
    raise SystemExit(main())
