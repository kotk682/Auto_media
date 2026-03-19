from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pathlib import Path
from app.core.database import init_db
from app.routers import projects, pipeline, tts, image, video


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    Path("media/audio").mkdir(parents=True, exist_ok=True)
    Path("media/images").mkdir(parents=True, exist_ok=True)
    Path("media/videos").mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="AutoMedia API", version="0.1.0", lifespan=lifespan)

app.include_router(projects.router)
app.include_router(pipeline.router)
app.include_router(tts.router)
app.include_router(image.router)
app.include_router(video.router)

app.mount("/media", StaticFiles(directory="media"), name="media")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}
