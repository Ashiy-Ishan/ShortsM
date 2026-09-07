"""core/downloader.py — download YouTube video to local mp4."""
from __future__ import annotations
import os
import glob
from pathlib import Path
import yt_dlp

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DOWNLOADS_DIR = DATA_DIR / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

def download_video(url: str, format_id: str = "best") -> dict:
    """Download video with specified format_id or best quality."""
    try:
        output_template = str(DOWNLOADS_DIR / "%(id)s.%(ext)s")

        if format_id and format_id != "best":
            ydl_format = f"{format_id}+bestaudio/best"
        else:
            ydl_format = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

        ydl_opts = {
            "format": ydl_format,
            "outtmpl": output_template,
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get("id")
            title = info.get("title", "video")
            duration = info.get("duration", 0)

            target_file = DOWNLOADS_DIR / f"{video_id}.mp4"
            if not target_file.exists():
                matches = list(DOWNLOADS_DIR.glob(f"{video_id}.*"))
                if matches:
                    target_file = matches[0]
                else:
                    return {"error": "Downloaded file not found."}

            filesize = target_file.stat().st_size if target_file.exists() else 0

            return {
                "id": video_id,
                "title": title,
                "duration": duration,
                "filepath": str(target_file),
                "filename": target_file.name,
                "filesize_mb": round(filesize / (1024 * 1024), 2),
            }
    except Exception as e:
        return {"error": str(e)}

