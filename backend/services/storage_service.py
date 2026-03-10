import logging
import os
from abc import ABC, abstractmethod

from backend.config import Settings

logger = logging.getLogger(__name__)


class StorageService(ABC):
    @abstractmethod
    async def upload(self, path: str, data: bytes) -> str:
        """Upload audio data. Returns the storage path."""
        pass

    @abstractmethod
    async def download(self, path: str) -> bytes:
        """Download audio data by path."""
        pass

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Delete audio data by path."""
        pass


class LocalStorageService(StorageService):
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    async def upload(self, path: str, data: bytes) -> str:
        filepath = os.path.join(self.base_dir, path)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(data)
        return filepath

    async def download(self, path: str) -> bytes:
        # path could be absolute (legacy) or relative
        filepath = path if os.path.isabs(path) else os.path.join(self.base_dir, path)
        with open(filepath, "rb") as f:
            return f.read()

    async def delete(self, path: str) -> None:
        filepath = path if os.path.isabs(path) else os.path.join(self.base_dir, path)
        if os.path.exists(filepath):
            os.remove(filepath)


class SupabaseStorageService(StorageService):
    def __init__(self, supabase_url: str, supabase_key: str, bucket: str):
        from supabase import create_client

        self.client = create_client(supabase_url, supabase_key)
        self.bucket = bucket
        self._ensure_bucket()

    def _ensure_bucket(self):
        """Ensure the storage bucket exists. Raises if it cannot be created."""
        try:
            self.client.storage.get_bucket(self.bucket)
            logger.info("Supabase bucket '%s' found", self.bucket)
            return
        except Exception:
            pass

        # Try to create with public: True (avoids RLS issues with anon key)
        for public in [False, True]:
            try:
                self.client.storage.create_bucket(
                    self.bucket,
                    options={"public": public},
                )
                logger.info(
                    "Created Supabase bucket '%s' (public=%s)", self.bucket, public
                )
                return
            except Exception as e:
                logger.debug("Bucket create attempt (public=%s): %s", public, e)

        raise RuntimeError(
            f"Cannot access or create Supabase bucket '{self.bucket}'. "
            "Please create it manually in the Supabase dashboard."
        )

    async def upload(self, path: str, data: bytes) -> str:
        # Remove existing file first (upsert)
        try:
            self.client.storage.from_(self.bucket).remove([path])
        except Exception:
            pass
        self.client.storage.from_(self.bucket).upload(
            path, data, file_options={"content-type": "application/octet-stream"}
        )
        return path

    async def download(self, path: str) -> bytes:
        response = self.client.storage.from_(self.bucket).download(path)
        return response

    async def delete(self, path: str) -> None:
        try:
            self.client.storage.from_(self.bucket).remove([path])
        except Exception:
            logger.warning("Failed to delete %s from storage", path)


# In-memory cache for audio during calls (avoids repeated downloads)
_audio_memory_cache: dict[str, bytes] = {}


async def get_cached_audio(storage: StorageService, path: str) -> bytes:
    """Download audio with in-memory caching for call performance."""
    if path in _audio_memory_cache:
        return _audio_memory_cache[path]
    data = await storage.download(path)
    _audio_memory_cache[path] = data
    return data


def invalidate_audio_cache(path: str) -> None:
    """Remove a path from the in-memory cache."""
    _audio_memory_cache.pop(path, None)


def create_storage_service(settings: Settings) -> StorageService:
    if settings.use_supabase_storage:
        try:
            return SupabaseStorageService(
                settings.supabase_url,
                settings.supabase_key,
                settings.supabase_storage_bucket,
            )
        except Exception as e:
            logger.warning(
                "Supabase Storage unavailable (%s), falling back to local storage",
                e,
            )
    return LocalStorageService(settings.audio_cache_dir)
