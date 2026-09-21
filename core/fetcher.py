"""core/fetcher.py — fetch video info + formats via yt-dlp or local video files."""
from __future__ import annotations
import subprocess
import json
from pathlib import Path
from core.security import validate_video_url

def get_local_video_info(path_str: str) -> dict:
    """Get metadata for local video file using ffprobe."""
    p = Path(path_str)
    if not p.exists() or not p.is_file():
        return {"error": f"File not found: {path_str}"}

    duration = 0.0
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(p)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0 and res.stdout.strip():
            duration = float(res.stdout.strip())
    except Exception:
        pass

    filesize = p.stat().st_size
    return {
        "title": p.stem,
        "duration": round(duration, 1),
        "thumbnail": "",
        "uploader": "Local File",
        "formats": [{
            "format_id": "local",
            "label": f"Local Original ({p.suffix.upper()}) · {round(filesize / (1024 * 1024), 1)} MB",
            "height": 1080,
            "ext": p.suffix.replace(".", ""),
            "size_mb": round(filesize / (1024 * 1024), 1),
        }]
    }

def fetch_video_info(url: str) -> dict:
    """Fetch video metadata and available formats."""
    try:
        cleaned_url = validate_video_url(url)
    except ValueError as exc:
        return {"error": str(exc)}

    # Check if input is a local file
    if Path(cleaned_url).exists() and Path(cleaned_url).is_file():
        return get_local_video_info(cleaned_url)

    import yt_dlp
    opts = {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": False,
        "ignoreerrors": False,
        "noplaylist": True,
        "extract_flat": False,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(cleaned_url, download=False)
            if not info:
                return {"error": "Video unavailable, private, or age-restricted."}

            formats, seen = [], set()
            for f in sorted(info.get("formats", []), key=lambda x: x.get("height") or 0, reverse=True):
                if f.get("vcodec") != "none" and f.get("height"):
                    height = f["height"]
                    fps    = f.get("fps", "")
                    ext    = f.get("ext", "")
                    fsize  = f.get("filesize") or f.get("filesize_approx")

                    size_str = f"{fsize / 1024 / 1024:.0f} MB" if fsize else ""

                    lbl = f"{height}p"
                    if fps: lbl += f" {int(fps)}fps"
                    lbl += f" · {ext.upper()}"
                    if size_str: lbl += f" · {size_str}"

                    key = f"{height}p-{fps}-{ext}"
                    if key not in seen:
                        seen.add(key)
                        formats.append({
                            "format_id": f["format_id"],
                            "label": lbl,
                            "height": height,
                            "ext": ext,
                            "size_mb": round(fsize / 1024 / 1024, 1) if fsize else None,
                        })

            return {
                "title":    info.get("title", "Untitled"),
                "duration": info.get("duration", 0),
                "thumbnail": info.get("thumbnail", ""),
                "uploader": info.get("uploader", ""),
                "formats":  formats,
            }
    except Exception as e:
        return {"error": f"Failed to fetch video: {str(e)}"}
