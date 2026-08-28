import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from core.fetcher import fetch_video_info

app = FastAPI(title="ShortM", version="2.0.0")

_here = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.join(_here, "..", "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

@app.get("/api/ping")
def ping():
    return {"status": "ok", "version": "2.0.0", "label": "URL Fetch"}

class FetchRequest(BaseModel):
    url: str

@app.post("/api/video/info")
def video_info(req: FetchRequest):
    return fetch_video_info(req.url)

@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND, "index.html"))
