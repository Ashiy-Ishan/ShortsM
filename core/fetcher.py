"""core/fetcher.py — fetch YouTube video info + format sizes via yt-dlp."""
from __future__ import annotations

def fetch_video_info(url: str) -> dict:
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "nocheckcertificate": True, "ignoreerrors": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return {"error": "Video unavailable or private."}

            formats, seen = [], set()
            for f in sorted(info.get("formats", []), key=lambda x: x.get("height") or 0, reverse=True):
                if f.get("vcodec") != "none" and f.get("height"):
                    height = f["height"]
                    fps    = f.get("fps", "")
                    ext    = f.get("ext", "")
                    fsize  = f.get("filesize") or f.get("filesize_approx")

                    if fsize:
                        size_str = f"{fsize / 1024 / 1024:.0f} MB"
                    else:
                        size_str = ""

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
        return {"error": str(e)}
