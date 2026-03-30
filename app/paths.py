from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_DIR = BASE_DIR / "media"
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"
FRONTEND_INDEX_FILE = FRONTEND_DIST_DIR / "index.html"

IMAGE_DIR = MEDIA_DIR / "images"
CHARACTER_DIR = MEDIA_DIR / "characters"
EPISODE_DIR = MEDIA_DIR / "episodes"
AUDIO_DIR = MEDIA_DIR / "audio"
VIDEO_DIR = MEDIA_DIR / "videos"
