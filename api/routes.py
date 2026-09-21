import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core.fetcher import fetch_video_info
from core.downloader import download_video
from core.transcriber import transcribe_video
from core.hook_detector import detect_hooks
from core.renderer import render_short, SHORTS_DIR
from core.security import validate_data_file
from core.jobs import JobManager

app = FastAPI(title="ShortsM", version="2.0.0")
logger = logging.getLogger("shortsm")
jobs = JobManager()

_here = Path(__file__).resolve().parent
PROJECT_ROOT = _here.parent
FRONTEND = PROJECT_ROOT / "frontend"
DATA_DIR = PROJECT_ROOT / "data"

DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "downloads").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "shorts").mkdir(parents=True, exist_ok=True)

# Mount static frontend assets and generated shorts only. Downloaded source
# videos and transcripts must not be directly browsable.
app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")
app.mount("/data/shorts", StaticFiles(directory=str(DATA_DIR / "shorts")), name="shorts")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' https: data:; media-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
        "font-src 'self' https://fonts.gstatic.com; script-src 'self'"
    )
    return response


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    logger.exception("Unhandled API error for %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "Unexpected server error. Check the application logs."},
    )

@app.get("/api/ping")
def ping():
    return {"status": "ok", "version": "2.0.0", "label": "ShortsM Full Pipeline"}

# 01 Source
class FetchRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)

@app.post("/api/video/info")
def video_info(req: FetchRequest):
    return fetch_video_info(req.url)

# 02 Download
class DownloadRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    format_id: str = Field(default="best", min_length=1, max_length=80)

@app.post("/api/video/download")
def download(req: DownloadRequest):
    job = jobs.create(lambda current_job: download_video(
        req.url,
        req.format_id,
        job=current_job,
    ))
    logger.info("Download job %s created", job.id)
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job not found."})
    return job.snapshot()


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    if not jobs.cancel(job_id):
        return JSONResponse(
            status_code=409,
            content={"error": "Job is missing or can no longer be cancelled."},
        )
    logger.info("Cancellation requested for job %s", job_id)
    return {"status": "cancelling", "job_id": job_id}

# 03 Transcribe
class TranscribeRequest(BaseModel):
    filepath: str = Field(min_length=1, max_length=1024)
    model_size: str = Field(default="tiny", max_length=20)

@app.post("/api/video/transcribe")
def transcribe(req: TranscribeRequest):
    try:
        validate_data_file(req.filepath, allow_short=False)
    except ValueError as exc:
        return {"error": str(exc)}
    return transcribe_video(req.filepath, req.model_size)

# 04 Detect Hooks
class HooksRequest(BaseModel):
    segments: list[dict] = Field(max_length=5000)
    min_duration: float = Field(default=15.0, ge=1, le=300)
    max_duration: float = Field(default=55.0, ge=1, le=300)

@app.post("/api/video/hooks")
def hooks(req: HooksRequest):
    if req.min_duration > req.max_duration:
        return {"error": "Minimum duration cannot exceed maximum duration.", "hooks": []}
    return {"hooks": detect_hooks(req.segments, req.min_duration, req.max_duration)}

# 05 Render Short
class RenderRequest(BaseModel):
    video_path: str = Field(min_length=1, max_length=1024)
    start_time: float = Field(ge=0, le=86400)
    end_time: float = Field(ge=0, le=86400)
    segments: list[dict] = Field(default_factory=list, max_length=5000)
    output_name: str | None = Field(default=None, max_length=110)
    with_subtitles: bool = True

@app.post("/api/video/render")
def render(req: RenderRequest):
    if req.end_time <= req.start_time or req.end_time - req.start_time > 300:
        return {"error": "Clip must be between 0 and 300 seconds."}
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
            "size_mb": round(mp4_path.stat().st_size / (1024 * 1024), 2),
            "created_at": mp4_path.stat().st_mtime,
            "video_url": f"/data/shorts/{mp4_path.name}",
            "thumbnail_url": f"/data/shorts/{thumb_path.name}" if thumb_path.exists() else "",
        })
    return {"shorts": shorts}

@app.get("/")
def index():
    return FileResponse(str(FRONTEND / "index.html"))
