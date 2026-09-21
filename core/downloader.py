"""core/downloader.py — download YouTube video or import local video to data/downloads."""
from __future__ import annotations
import subprocess
from pathlib import Path
import yt_dlp
from core.security import validate_video_url
from core.jobs import Job

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DOWNLOADS_DIR = DATA_DIR / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

def ensure_mp4(filepath: Path) -> Path:
    """Ensure video file is MP4 container for fast seeking and processing."""
    if filepath.suffix.lower() == ".mp4":
        return filepath

    target_mp4 = filepath.with_suffix(".mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(filepath),
        "-c:v", "copy",
        "-c:a", "aac",
        str(target_mp4)
    ]
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if res.returncode == 0 and target_mp4.exists():
        return target_mp4
    return filepath

def download_video(
    url: str,
    format_id: str = "best",
    *,
    job: Job | None = None,
) -> dict:
    """Download video with specified format_id or best quality, or import local video file."""
    try:
        cleaned_url = validate_video_url(url)
    except ValueError as exc:
        return {"error": str(exc)}

    def log(message: str, level: str = "info") -> None:
        if job:
            job.log(message, level)

    def check_cancelled() -> None:
        if job and job.cancel_event.is_set():
            raise InterruptedError("Download cancelled by user.")

    # Handle local file directly
    local_p = Path(cleaned_url)
    if local_p.exists() and local_p.is_file():
        dest = DOWNLOADS_DIR / local_p.name
        if dest.resolve() != local_p.resolve():
            total = local_p.stat().st_size
            copied = 0
            log(f"Copying local file: {local_p.name}")
            with local_p.open("rb") as source, dest.open("wb") as target:
                while chunk := source.read(1024 * 1024):
                    check_cancelled()
                    target.write(chunk)
                    copied += len(chunk)
                    if job:
                        with job.lock:
                            job.progress = copied / total * 100 if total else 100
                            job.message = f"Copying local file ({job.progress:.1f}%)"
        final_file = ensure_mp4(dest)
        filesize = final_file.stat().st_size
        return {
            "id": final_file.stem,
            "title": final_file.stem,
            "duration": 0,
            "filepath": str(final_file),
            "filename": final_file.name,
            "filesize_mb": round(filesize / (1024 * 1024), 2),
        }

    try:
        output_template = str(DOWNLOADS_DIR / "%(id)s.%(ext)s")

        if format_id and format_id not in ("best", "local"):
            ydl_format = f"{format_id}+bestaudio/bestvideo+bestaudio/best"
        else:
            ydl_format = "bestvideo+bestaudio/best"

        def progress_hook(data: dict) -> None:
            check_cancelled()
            if not job:
                return
            status = data.get("status")
            if status == "downloading":
                downloaded = data.get("downloaded_bytes", 0)
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                with job.lock:
                    job.progress = downloaded / total * 100 if total else 0
                    job.speed = data.get("_speed_str", "")
                    job.eta = data.get("_eta_str", "")
                    job.message = (
                        f"Downloading {job.progress:.1f}%"
                        f" · {job.speed or 'calculating speed'}"
                        f" · ETA {job.eta or '--'}"
                    )
            elif status == "finished":
                log("Download stream finished; merging audio and video.")

        ydl_opts = {
            "format": ydl_format,
            "outtmpl": output_template,
            "merge_output_format": "mp4",
            "quiet": False,
            "no_warnings": True,
            "nocheckcertificate": False,
            "noplaylist": True,
            "extract_flat": False,
            "progress_hooks": [progress_hook],
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            }
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(cleaned_url, download=True)
            if not info:
                return {"error": "Could not extract video info. Video might be unavailable."}

            video_id = info.get("id")
            title = info.get("title", "video")
            duration = info.get("duration", 0)

            target_file = DOWNLOADS_DIR / f"{video_id}.mp4"
            if not target_file.exists():
                matches = list(DOWNLOADS_DIR.glob(f"{video_id}.*"))
                if matches:
                    target_file = matches[0]
                else:
                    return {"error": "Download completed but target file was not found in directory."}

            final_mp4 = ensure_mp4(target_file)
            filesize = final_mp4.stat().st_size if final_mp4.exists() else 0

            return {
                "id": video_id,
                "title": title,
                "duration": duration,
                "filepath": str(final_mp4),
                "filename": final_mp4.name,
                "filesize_mb": round(filesize / (1024 * 1024), 2),
            }
    except InterruptedError as exc:
        if local_p.exists() and local_p.is_file() and "dest" in locals() and dest.exists():
            dest.unlink(missing_ok=True)
        log(str(exc), "warning")
        return {"error": str(exc), "cancelled": True}
    except Exception as e:
        if job and job.cancel_event.is_set():
            log("Download cancelled by user.", "warning")
            return {"error": "Download cancelled by user.", "cancelled": True}
        log(f"Download failed: {e}", "error")
        return {"error": f"Download failed: {str(e)}"}
