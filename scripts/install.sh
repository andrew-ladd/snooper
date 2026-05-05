#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/install.sh [options]

Create a virtual environment and install snooper.

Options:
  --python PATH       Python interpreter to use. Defaults to the first Python
                      3.10+ found from SNOOPER_PYTHON, python3.13, python3.12,
                      python3.11, python3.10, or python3.
  --venv PATH         Virtual environment path. Defaults to .venv.
  --link             Symlink snooper into a user bin directory.
  --bin-dir PATH     Directory to receive the snooper symlink when --link is
                      used. Defaults to ~/.local/bin.
  --alias            Add or update a persistent shell alias:
                      alias snooper='<venv>/bin/snooper'
  --alias-file PATH  Shell startup file to update when --alias is used.
                      Defaults to ~/.zshrc for zsh, ~/.bashrc for bash, or
                      ~/.profile otherwise.
  --no-dev           Install runtime dependencies only, without test extras.
  -h, --help         Show this help.

Environment:
  SNOOPER_PYTHON      Preferred Python interpreter when --python is omitted.
  SNOOPER_BIN_DIR     Directory to receive the snooper symlink when --link is
                      used.
  SNOOPER_ALIAS_FILE  Shell startup file to update when --alias is used.
USAGE
}

log() {
  printf '==> %s\n' "$*"
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
venv_path="$repo_root/.venv"
python_path="${SNOOPER_PYTHON:-}"
bin_dir="${SNOOPER_BIN_DIR:-"$HOME/.local/bin"}"
alias_file="${SNOOPER_ALIAS_FILE:-}"
install_link=0
install_alias=0
install_target='.[test]'

while [ "$#" -gt 0 ]; do
  case "$1" in
    --python)
      [ "$#" -ge 2 ] || die "--python requires a path"
      python_path="$2"
      shift 2
      ;;
    --venv)
      [ "$#" -ge 2 ] || die "--venv requires a path"
      case "$2" in
        /*) venv_path="$2" ;;
        *) venv_path="$repo_root/$2" ;;
      esac
      shift 2
      ;;
    --link)
      install_link=1
      shift
      ;;
    --bin-dir)
      [ "$#" -ge 2 ] || die "--bin-dir requires a path"
      bin_dir="$2"
      install_link=1
      shift 2
      ;;
    --alias)
      install_alias=1
      shift
      ;;
    --alias-file)
      [ "$#" -ge 2 ] || die "--alias-file requires a path"
      alias_file="$2"
      install_alias=1
      shift 2
      ;;
    --no-dev)
      install_target='.'
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

supports_python_version() {
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1
}

find_python() {
  if [ -n "$python_path" ]; then
    command -v "$python_path" >/dev/null 2>&1 || die "Python not found: $python_path"
    supports_python_version "$python_path" || die "$python_path must be Python 3.10 or newer"
    printf '%s\n' "$python_path"
    return
  fi

  for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && supports_python_version "$candidate"; then
      command -v "$candidate"
      return
    fi
  done

  die "Python 3.10 or newer is required. Install it, or rerun with --python PATH."
}

default_alias_file() {
  case "$(basename "${SHELL:-}")" in
    zsh) printf '%s\n' "$HOME/.zshrc" ;;
    bash) printf '%s\n' "$HOME/.bashrc" ;;
    *) printf '%s\n' "$HOME/.profile" ;;
  esac
}

expand_home_path() {
  case "$1" in
    "~") printf '%s\n' "$HOME" ;;
    "~/"*) printf '%s/%s\n' "$HOME" "${1#"~/"}" ;;
    *) printf '%s\n' "$1" ;;
  esac
}

path_contains_dir() {
  local target_dir="$1"
  case ":$PATH:" in
    *":$target_dir:"*) return 0 ;;
    *) return 1 ;;
  esac
}

install_snooper_link() {
  local target_dir
  local target_path

  target_dir="$(expand_home_path "$bin_dir")"
  target_path="$target_dir/snooper"

  mkdir -p "$target_dir"
  if [ -e "$target_path" ] && [ ! -L "$target_path" ]; then
    die "refusing to replace existing non-symlink: $target_path"
  fi

  ln -sfn "$venv_snooper" "$target_path"
  printf '%s\n' "$target_path"
}

shell_quote() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}

install_snooper_alias() {
  local target_file="$alias_file"
  if [ -z "$target_file" ]; then
    target_file="$(default_alias_file)"
  fi
  target_file="$(expand_home_path "$target_file")"

  local start_marker="# snooper alias: managed by scripts/install.sh"
  local end_marker="# end snooper alias"
  local alias_line="alias snooper=$(shell_quote "$venv_snooper")"
  local tmp_file

  mkdir -p "$(dirname "$target_file")"
  touch "$target_file"
  tmp_file="$(mktemp)"

  awk -v start="$start_marker" -v end="$end_marker" '
    $0 == start { skipping = 1; next }
    $0 == end { skipping = 0; next }
    !skipping { print }
  ' "$target_file" > "$tmp_file"

  {
    cat "$tmp_file"
    printf '\n%s\n%s\n%s\n' "$start_marker" "$alias_line" "$end_marker"
  } > "$target_file"

  rm -f "$tmp_file"
  printf '%s\n' "$target_file"
}

python_bin="$(find_python)"

cd "$repo_root"

log "Using Python: $("$python_bin" -c 'import sys; print(sys.executable)')"
log "Creating virtual environment: $venv_path"
"$python_bin" -m venv "$venv_path"

venv_python="$venv_path/bin/python"
venv_snooper="$venv_path/bin/snooper"

log "Upgrading packaging tools"
"$venv_python" -m pip install --upgrade pip setuptools wheel

log "Installing snooper: $install_target"
"$venv_python" -m pip install --no-build-isolation -e "$install_target"

log "Checking CLI"
"$venv_snooper" --help >/dev/null

if ! command -v ffmpeg >/dev/null 2>&1; then
  printf 'warning: ffmpeg was not found. snooper can try to install it during video downloads, or install it now with your package manager.\n' >&2
fi

link_message=""
if [ "$install_link" -eq 1 ]; then
  log "Installing command symlink"
  linked_snooper="$(install_snooper_link)"
  linked_dir="$(dirname "$linked_snooper")"
  if path_contains_dir "$linked_dir"; then
    link_message="The snooper command is on PATH:
  snooper --help"
  else
    link_message="A snooper command symlink was added at:
  $linked_snooper

Add this directory to PATH if your shell does not already include it:
  export PATH=\"$linked_dir:\$PATH\""
  fi
fi

alias_message="Or activate the environment:
  source \"$venv_path/bin/activate\""

if [ "$install_alias" -eq 1 ]; then
  log "Installing shell alias"
  updated_alias_file="$(install_snooper_alias)"
  alias_message="The 'snooper' alias was added to:
  $updated_alias_file

Reload your shell startup file:
  source \"$updated_alias_file\""
fi

cat <<EOF

Installed snooper successfully.

Run it with:
  $venv_snooper --help

$link_message

$alias_message
EOF
