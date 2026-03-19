from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.story import router

app = FastAPI(title="Auto Media API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

