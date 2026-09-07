import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.fetcher import fetch_video_info
from core.downloader import download_video
from core.transcriber import transcribe_video
from core.hook_detector import detect_hooks
from core.renderer import render_short, SHORTS_DIR
from core.uploader import upload_to_imagekit

app = FastAPI(title="ShortsM", version="2.0.0")

_here = Path(__file__).resolve().parent
PROJECT_ROOT = _here.parent
FRONTEND = PROJECT_ROOT / "frontend"
DATA_DIR = PROJECT_ROOT / "data"

DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "downloads").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "shorts").mkdir(parents=True, exist_ok=True)

# Mount static frontend assets and generated data
app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")
app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")

@app.get("/api/ping")
def ping():
    return {"status": "ok", "version": "2.0.0", "label": "ShortsM Full Pipeline"}

# 01 Source
class FetchRequest(BaseModel):
    url: str

@app.post("/api/video/info")
def video_info(req: FetchRequest):
    return fetch_video_info(req.url)

# 02 Download
class DownloadRequest(BaseModel):
    url: str
    format_id: str = "best"

@app.post("/api/video/download")
def download(req: DownloadRequest):
    return download_video(req.url, req.format_id)

# 03 Transcribe
class TranscribeRequest(BaseModel):
    filepath: str
    model_size: str = "tiny"

@app.post("/api/video/transcribe")
def transcribe(req: TranscribeRequest):
    return transcribe_video(req.filepath, req.model_size)

# 04 Detect Hooks
class HooksRequest(BaseModel):
    segments: list[dict]
    min_duration: float = 15.0
    max_duration: float = 55.0

@app.post("/api/video/hooks")
def hooks(req: HooksRequest):
    return {"hooks": detect_hooks(req.segments, req.min_duration, req.max_duration)}

# 05 Render Short
class RenderRequest(BaseModel):
    video_path: str
    start_time: float
    end_time: float
    segments: list[dict] = []
    output_name: str | None = None
    with_subtitles: bool = True

@app.post("/api/video/render")
def render(req: RenderRequest):
    return render_short(
        video_path=req.video_path,
        start_time=req.start_time,
        end_time=req.end_time,
        segments=req.segments,
        output_name=req.output_name,
        with_subtitles=req.with_subtitles
    )

# 06 Gallery
@app.get("/api/gallery")
def get_gallery():
    shorts = []
    for mp4_path in sorted(SHORTS_DIR.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True):
        thumb_path = mp4_path.with_suffix(".jpg")
        shorts.append({
            "id": mp4_path.stem,
            "filename": mp4_path.name,
            "filepath": str(mp4_path),
            "size_mb": round(mp4_path.stat().st_size / (1024 * 1024), 2),
            "created_at": mp4_path.stat().st_mtime,
            "video_url": f"/data/shorts/{mp4_path.name}",
            "thumbnail_url": f"/data/shorts/{thumb_path.name}" if thumb_path.exists() else "",
        })
    return {"shorts": shorts}

# 07 Upload
class UploadRequest(BaseModel):
    filepath: str
    folder: str = "/shorts"

@app.post("/api/upload")
def upload(req: UploadRequest):
    return upload_to_imagekit(req.filepath, req.folder)

@app.get("/")
def index():
    return FileResponse(str(FRONTEND / "index.html"))
