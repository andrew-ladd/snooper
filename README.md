# snooper

<img src="https://www.absolutegeeks.com/wp-content/uploads/2023/11/Screenshot-2023-11-30-at-12.41.26%E2%80%AFPM.png" alt="Reddit Snoo mascot" width="180">

`snooper` downloads media associated with Reddit posts from the command line.
Give it a Reddit post URL and it will save the post's images, galleries, videos,
and supported external media links.

It is built for:

- Reddit-hosted images: `jpg`, `jpeg`, `png`, `webp`, and `gif`
- Reddit galleries, preserving gallery order and captions in metadata
- Reddit-hosted videos, using `ffmpeg` to merge audio/video
- External media links supported by optional `yt-dlp`, such as many common
  video and image-hosting sites
- `reddit.com`, `old.reddit.com`, mobile Reddit URLs, and `redd.it` short links

## Requirements

- Python 3.10 or newer
- `ffmpeg` for Reddit videos with audio
- Internet access to Reddit and any external media host

## Setup

Clone the repository, create a virtual environment, and install the CLI:

```bash
git clone https://github.com/andrew-ladd/snooper.git
cd snooper
scripts/install.sh --link
```

The script finds Python 3.10 or newer, creates `.venv`, installs a lean launcher
that runs the local source tree, and checks that the `snooper` command is
available. This default install does not install `yt-dlp`; Reddit-hosted images,
galleries, and videos work without it. If you later download an external media
link that needs `yt-dlp`, snooper installs it automatically in the active
environment. With `--link`, it also symlinks the command into `~/.local/bin` so
you can run:

```bash
snooper --help
```

If `~/.local/bin` is not already on your `PATH`, add it in your shell startup
file:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

To choose a specific Python interpreter or virtualenv path:

```bash
scripts/install.sh --link --python /path/to/python3 --venv .venv
```

To preinstall external media site support through `yt-dlp`:

```bash
scripts/install.sh --link --with-external
```

For development dependencies:

```bash
scripts/install.sh --link --dev
```

To choose a different directory for the `snooper` command:

```bash
scripts/install.sh --bin-dir "$HOME/bin"
```

An alias also works for interactive shell use:

```bash
scripts/install.sh --alias
```

The alias option writes a managed block like
`alias snooper='/path/to/.venv/bin/snooper'` to `~/.zshrc` for zsh, `~/.bashrc`
for bash, or `~/.profile` otherwise. Use `--alias-file PATH` to choose a
different startup file. After installing an alias, restart your shell or source
the startup file printed by the script.

Manual setup is equivalent to:

```bash
python3 -m venv .venv
cat > .venv/bin/snooper <<'SH'
#!/usr/bin/env bash
export PYTHONPATH="$(pwd)/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$(pwd)/.venv/bin/python" -m snooper.cli "$@"
SH
chmod +x .venv/bin/snooper
```

Run the tool through the virtualenv:

```bash
.venv/bin/snooper --help
```

If `ffmpeg` is missing, `snooper` will try to install it with a known package
manager: `brew`, `apt-get`, `dnf`, `yum`, `pacman`, or `choco`. Disable that
behavior with `--no-install-ffmpeg`.

External media links use optional `yt-dlp`. If it is missing, snooper installs
it automatically before continuing. To install it yourself:

```bash
.venv/bin/python -m pip install 'yt-dlp>=2025.1.0'
```

## Uninstall

Remove the virtual environment, the default `~/.local/bin/snooper` symlink if it
points at that environment, and the managed shell alias block if present:

```bash
scripts/uninstall.sh
```

If you installed with a custom path, pass the same location:

```bash
scripts/uninstall.sh --venv /path/to/.venv --bin-dir "$HOME/bin"
```

Downloaded media is not removed.

## Usage

Download a Reddit video post:

```bash
snooper https://www.reddit.com/r/nhl/comments/1t43i14/leo_carlsson_with_a_stunning_move_to_set_up/
```

Download from a short link:

```bash
snooper https://redd.it/1t43i14
```

Choose an output directory:

```bash
snooper -o ./media https://redd.it/1t43i14
```

Preview work without writing files:

```bash
snooper --dry-run https://redd.it/1t43i14
```

Download several posts at once:

```bash
snooper https://redd.it/post1 https://redd.it/post2
```

Read URLs from stdin:

```bash
cat urls.txt | snooper -
```

Include NSFW posts explicitly:

```bash
snooper --include-nsfw https://www.reddit.com/r/example/comments/abc123/title/
```

## Output

Downloads go into `~/Downloads` by default. Each Reddit post gets its own folder:

```text
~/Downloads/
  nhl-1t43i14-Leo-Carlsson-with-a-stunning-move-to-set-up/
    001-Leo-Carlsson-with-a-stunning-move-to-set-up.mp4
    metadata.json
```

Existing files are skipped with a unique suffix unless `--overwrite` is passed.
Each post folder includes `metadata.json` unless `--no-metadata` is passed.

## Options

```text
-o, --output DIR        Write files under DIR instead of ~/Downloads
--include-nsfw         Allow downloads from posts marked NSFW
--overwrite            Replace existing files
--dry-run              Show what would be downloaded without writing files
--no-metadata          Do not write metadata.json
--no-install-ffmpeg    Do not try to install ffmpeg automatically
-q, --quiet            Only print warnings and errors
```

## Development

Run the tests:

```bash
.venv/bin/python -m pytest
```

Run a live dry-run against the example post:

```bash
snooper --dry-run --no-install-ffmpeg https://www.reddit.com/r/nhl/comments/1t43i14/leo_carlsson_with_a_stunning_move_to_set_up/
```

The project intentionally keeps direct Reddit parsing small. Broad external
site support is delegated to lazily installed `yt-dlp`.
