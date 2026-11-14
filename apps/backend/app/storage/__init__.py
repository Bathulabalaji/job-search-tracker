from app.core.config import Settings
from app.storage.object_store import (
    DisabledObjectStore,
    LocalObjectStore,
    ObjectStore,
    S3ObjectStore,
    StorageDisabled,
)


def build_object_store(settings: Settings) -> ObjectStore:
    """S3-compatible storage when configured (Cloudflare R2 in production), a local folder for
    development, otherwise a store that refuses uploads with a clear error."""
    if settings.object_store_bucket and settings.object_store_access_key_id:
        return S3ObjectStore(
            bucket=settings.object_store_bucket,
            endpoint_url=settings.object_store_endpoint_url or None,
            access_key_id=settings.object_store_access_key_id,
            secret_access_key=settings.object_store_secret_access_key,
            region=settings.object_store_region,
        )
    if settings.object_store_local_dir:
        return LocalObjectStore(settings.object_store_local_dir)
    return DisabledObjectStore()


__all__ = [
    "DisabledObjectStore",
    "LocalObjectStore",
    "ObjectStore",
    "S3ObjectStore",
    "StorageDisabled",
    "build_object_store",
]
