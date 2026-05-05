from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class InstallAttempt:
    attempted: bool
    command: tuple[str, ...] | None = None
    success: bool = False
    message: str = ""


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def install_ffmpeg_if_possible(*, dry_run: bool = False) -> InstallAttempt:
    if ffmpeg_available():
        return InstallAttempt(False, success=True, message="ffmpeg is already installed")

    command = _install_command()
    if command is None:
        return InstallAttempt(
            False,
            success=False,
            message=(
                "ffmpeg is required for Reddit videos with audio. Install it with "
                "Homebrew, apt, dnf, yum, pacman, Chocolatey, or from https://ffmpeg.org/."
            ),
        )

    if dry_run:
        return InstallAttempt(True, command, False, "ffmpeg would be installed")

    try:
        subprocess.run(command, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        return InstallAttempt(
            True,
            command,
            False,
            f"failed to install ffmpeg with {' '.join(command)}: {exc}",
        )

    return InstallAttempt(True, command, ffmpeg_available(), "ffmpeg installed")


def _install_command() -> tuple[str, ...] | None:
    if shutil.which("brew"):
        return ("brew", "install", "ffmpeg")
    if shutil.which("apt-get"):
        return ("sudo", "apt-get", "install", "-y", "ffmpeg")
    if shutil.which("dnf"):
        return ("sudo", "dnf", "install", "-y", "ffmpeg")
    if shutil.which("yum"):
        return ("sudo", "yum", "install", "-y", "ffmpeg")
    if shutil.which("pacman"):
        return ("sudo", "pacman", "-S", "--noconfirm", "ffmpeg")
    if sys.platform.startswith("win") and shutil.which("choco"):
        return ("choco", "install", "ffmpeg", "-y")
    return None

