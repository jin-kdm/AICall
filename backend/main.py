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
    from backend.services.storage_service import (
        SupabaseStorageService,
        create_storage_service,
    )

    info = {
        "supabase_configured": settings.use_supabase_storage,
        "supabase_url": settings.supabase_url[:30] + "..." if settings.supabase_url else "",
        "supabase_key_set": bool(settings.supabase_key),
        "supabase_bucket": settings.supabase_storage_bucket,
        "ws_base_url": settings.effective_ws_base_url,
    }

    # Try Supabase directly to capture the exact error
    if settings.use_supabase_storage:
        try:
            supa = SupabaseStorageService(
                settings.supabase_url,
                settings.supabase_key,
                settings.supabase_storage_bucket,
            )
            info["supabase_init"] = "ok"
            # Test write/read
            await supa.upload("_test.bin", b"test")
            data = await supa.download("_test.bin")
            await supa.delete("_test.bin")
            info["supabase_read_write"] = "ok"
        except Exception as e:
            info["supabase_init"] = f"FAILED: {type(e).__name__}: {e}"

    storage = create_storage_service(settings)
    info["active_storage"] = type(storage).__name__

    return info


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scenarios_router, prefix="/api")
app.include_router(twilio_router)