import logging
import os
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    logger.error("Unhandled error: %s\n%s", exc, tb)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/debug/storage")
async def debug_storage():
    """Check which storage backend is active and test connectivity."""
    from backend.services.storage_service import create_storage_service

    storage = create_storage_service(settings)
    storage_type = type(storage).__name__

    # Test write/read/delete
    test_path = "_health_check_test.bin"
    test_data = b"healthcheck"
    try:
        await storage.upload(test_path, test_data)
        read_back = await storage.download(test_path)
        await storage.delete(test_path)
        ok = read_back == test_data
    except Exception as e:
        ok = False
        return {
            "storage_type": storage_type,
            "ok": False,
            "error": str(e),
            "supabase_configured": settings.use_supabase_storage,
        }

    return {
        "storage_type": storage_type,
        "ok": ok,
        "supabase_configured": settings.use_supabase_storage,
        "ws_base_url": settings.effective_ws_base_url,
    }


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scenarios_router, prefix="/api")
app.include_router(twilio_router)