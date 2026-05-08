#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/uninstall.sh [options]

Remove files created by scripts/install.sh.

Options:
  --venv PATH         Virtual environment path to remove. Defaults to .venv.
  --bin-dir PATH     Directory containing the snooper symlink. Defaults to
                      ~/.local/bin or SNOOPER_BIN_DIR.
  --alias-file PATH  Shell startup file containing the managed snooper alias.
                      Defaults to ~/.zshrc for zsh, ~/.bashrc for bash, or
                      ~/.profile otherwise.
  --keep-venv        Do not remove the virtual environment.
  --keep-link        Do not remove the snooper symlink.
  --keep-alias       Do not remove the managed shell alias block.
  -h, --help         Show this help.

Environment:
  SNOOPER_BIN_DIR     Directory containing the snooper symlink.
  SNOOPER_ALIAS_FILE  Shell startup file containing the managed snooper alias.
USAGE
}

log() {
  printf '==> %s\n' "$*"
}

warn() {
  printf 'warning: %s\n' "$*" >&2
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
venv_path="$repo_root/.venv"
bin_dir="${SNOOPER_BIN_DIR:-"$HOME/.local/bin"}"
alias_file="${SNOOPER_ALIAS_FILE:-}"
remove_venv=1
remove_link=1
remove_alias=1

while [ "$#" -gt 0 ]; do
  case "$1" in
    --venv)
      [ "$#" -ge 2 ] || die "--venv requires a path"
      case "$2" in
        /*) venv_path="$2" ;;
        *) venv_path="$repo_root/$2" ;;
      esac
      shift 2
      ;;
    --bin-dir)
      [ "$#" -ge 2 ] || die "--bin-dir requires a path"
      bin_dir="$2"
      shift 2
      ;;
    --alias-file)
      [ "$#" -ge 2 ] || die "--alias-file requires a path"
      alias_file="$2"
      shift 2
      ;;
    --keep-venv)
      remove_venv=0
      shift
      ;;
    --keep-link)
      remove_link=0
      shift
      ;;
    --keep-alias)
      remove_alias=0
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

is_safe_venv_path() {
  case "$venv_path" in
    ""|"/"|"$HOME"|"$repo_root") return 1 ;;
    *) return 0 ;;
  esac
}

remove_snooper_link() {
  local target_dir
  local target_path
  local expected_target
  local actual_target

  target_dir="$(expand_home_path "$bin_dir")"
  target_path="$target_dir/snooper"
  expected_target="$venv_path/bin/snooper"

  if [ ! -e "$target_path" ] && [ ! -L "$target_path" ]; then
    log "No snooper symlink found at $target_path"
    return
  fi

  if [ ! -L "$target_path" ]; then
    warn "not removing non-symlink: $target_path"
    return
  fi

  actual_target="$(readlink "$target_path")"
  if [ "$actual_target" != "$expected_target" ]; then
    warn "not removing $target_path; it points to $actual_target"
    return
  fi

  rm "$target_path"
  log "Removed symlink: $target_path"
}

remove_snooper_alias() {
  local target_file="$alias_file"
  local start_marker="# snooper alias: managed by scripts/install.sh"
  local end_marker="# end snooper alias"
  local tmp_file

  if [ -z "$target_file" ]; then
    target_file="$(default_alias_file)"
  fi
  target_file="$(expand_home_path "$target_file")"

  if [ ! -f "$target_file" ]; then
    log "No alias file found at $target_file"
    return
  fi

  if ! grep -Fqx "$start_marker" "$target_file"; then
    log "No managed snooper alias found in $target_file"
    return
  fi

  tmp_file="$(mktemp)"
  awk -v start="$start_marker" -v end="$end_marker" '
    $0 == start { skipping = 1; next }
    $0 == end { skipping = 0; next }
    !skipping { print }
  ' "$target_file" > "$tmp_file"
  mv "$tmp_file" "$target_file"
  log "Removed managed alias block from $target_file"
}

remove_snooper_venv() {
  if [ ! -e "$venv_path" ]; then
    log "No virtual environment found at $venv_path"
    return
  fi

  is_safe_venv_path || die "refusing to remove unsafe venv path: $venv_path"

  if [ ! -f "$venv_path/bin/snooper" ] || ! grep -Fq "$repo_root/src" "$venv_path/bin/snooper"; then
    die "refusing to remove $venv_path because it does not look like a snooper install"
  fi

  rm -rf "$venv_path"
  log "Removed virtual environment: $venv_path"
}

if [ "$remove_link" -eq 1 ]; then
  remove_snooper_link
fi

if [ "$remove_alias" -eq 1 ]; then
  remove_snooper_alias
fi

if [ "$remove_venv" -eq 1 ]; then
  remove_snooper_venv
fi

cat <<EOF

Uninstalled snooper files managed by scripts/install.sh.

Downloaded media was not touched.
EOF
