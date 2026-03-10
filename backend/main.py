import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import init_db
from backend.routers.scenarios import router as scenarios_router
from backend.routers.twilio import router as twilio_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    os.makedirs(settings.audio_cache_dir, exist_ok=True)
    yield


app = FastAPI(title="AICall", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/buildcheck")
async def buildcheck():
    return {"version": "0dd1fff"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scenarios_router, prefix="/api")
app.include_router(twilio_router)