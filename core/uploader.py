"""core/uploader.py — upload generated shorts or media to ImageKit CDN."""
from __future__ import annotations
import os
from pathlib import Path

DEFAULT_PRIVATE_KEY = os.getenv("IMAGEKIT_PRIVATE_KEY", "private_5cDwgSe8Ss2Rlk9HotSK77RoQM8=")
DEFAULT_ENDPOINT = os.getenv("IMAGEKIT_URL_ENDPOINT", "https://ik.imagekit.io/x2eerczu0")

def upload_to_imagekit(
    file_path: str,
    folder: str = "/shorts",
    private_key: str | None = None
) -> dict:
    """Upload media file to ImageKit."""
    p = Path(file_path)
    if not p.exists():
        return {"error": f"File not found: {file_path}"}

    key = private_key or DEFAULT_PRIVATE_KEY
    if not key:
        return {"error": "ImageKit private key is missing."}

    try:
        from imagekitio import ImageKit
        ik = ImageKit(private_key=key)

        response = ik.files.upload(
            file=p,
            file_name=p.name,
            folder=folder,
            use_unique_file_name=True,
            tags=["shortsm", "shorts"]
        )

        return {
            "success": True,
            "url": getattr(response, "url", ""),
            "file_id": getattr(response, "file_id", ""),
            "name": getattr(response, "name", p.name),
            "folder": folder,
            "endpoint": DEFAULT_ENDPOINT,
        }
    except Exception as e:
        return {"error": str(e)}

