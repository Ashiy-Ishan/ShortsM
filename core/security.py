"""Shared validation helpers for the local ShortsM API."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = (PROJECT_ROOT / "data").resolve()
DOWNLOADS_DIR = (DATA_DIR / "downloads").resolve()
SHORTS_DIR = (DATA_DIR / "shorts").resolve()
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v"}


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def validate_data_file(path_value: str, *, allow_short: bool = True) -> Path:
    """Resolve a media path and ensure it is an existing file owned by the app."""
    if not path_value or len(path_value) > 1024:
        raise ValueError("A valid media file path is required.")

    path = Path(path_value).expanduser().resolve()
    allowed_roots = [DOWNLOADS_DIR]
    if allow_short:
        allowed_roots.append(SHORTS_DIR)

    if not any(is_within(path, root) for root in allowed_roots):
        raise ValueError("Media files must be inside the ShortsM data directory.")
    if not path.is_file():
        raise ValueError("Media file was not found.")
    if path.suffix.lower() not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValueError("Unsupported media file type.")
    return path


def validate_video_url(value: str) -> str:
    cleaned = value.strip().strip('"').strip("'")
    if not cleaned or len(cleaned) > 2048:
        raise ValueError("Please provide a valid YouTube URL or local video file path.")

    parsed = urlparse(cleaned)
    if parsed.scheme in {"http", "https"}:
        host = (parsed.hostname or "").lower().rstrip(".")
        allowed = host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}
        if not allowed:
            raise ValueError("Only YouTube URLs are supported.")
        return cleaned

    return cleaned


def safe_output_name(value: str | None) -> str | None:
    if not value:
        return None
    name = Path(value).name
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}", name):
        raise ValueError("Output name contains unsupported characters.")
    return name

