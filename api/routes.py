import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(title="ShortsM",version="1.0")

_here =os.path.dirname(os.path.abspath(__file__))
FRONTEND=os.path.join(_here,"..","frontend")

app.mount("/static",StaticFiles(directory=FRONTEND),name="static")

@app.get("/api/ping")
def ping():
    return {"status":"ok","version":"1.0"}
@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND,"index.html"))

