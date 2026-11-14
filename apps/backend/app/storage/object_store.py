"""Where uploaded files live. The database only ever holds a key."""

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from app.core.errors import AuthError

logger = logging.getLogger("app.storage")
_SAFE_KEY = re.compile(r"^[A-Za-z0-9_./-]+$")


class StorageDisabled(AuthError):
    """No object storage is configured on this server."""

    def __init__(self, message: str = "File uploads are not enabled on this server.") -> None:
        super().__init__("storage_disabled", message, 503)


@dataclass(frozen=True)
class StoredObject:
    key: str
    modified: datetime


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def list_objects(self, prefix: str) -> list[StoredObject]:
        """Every object whose key starts with `prefix` (used to find orphans)."""
        ...

    def presigned_get_url(self, key: str, *, filename: str, expires_seconds: int) -> str | None:
        """A direct download link, or None when this backend cannot make one (the API then
        serves the bytes itself through a short-lived signed link)."""
        ...


def _check_key(key: str) -> None:
    if not _SAFE_KEY.match(key) or ".." in key or key.startswith("/"):
        raise ValueError(f"unsafe storage key: {key!r}")


class S3ObjectStore:
    """Any S3-compatible bucket: Cloudflare R2, AWS S3, MinIO. boto3 is imported lazily so the
    rest of the app never pays for it."""

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None,
        access_key_id: str,
        secret_access_key: str,
        region: str = "auto",
    ) -> None:
        self.bucket = bucket
        self._client = _s3_client(endpoint_url, access_key_id, secret_access_key, region)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        _check_key(key)
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        _check_key(key)
        body = self._client.get_object(Bucket=self.bucket, Key=key)["Body"]
        return bytes(body.read())

    def delete(self, key: str) -> None:
        _check_key(key)
        self._client.delete_object(Bucket=self.bucket, Key=key)

    def list_objects(self, prefix: str) -> list[StoredObject]:
        _check_key(prefix)
        found: list[StoredObject] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                found.append(StoredObject(item["Key"], item["LastModified"]))
        return found

    def presigned_get_url(self, key: str, *, filename: str, expires_seconds: int) -> str | None:
        _check_key(key)
        safe = re.sub(r"[^A-Za-z0-9._ -]", "_", filename) or "resume.pdf"
        url: str = self._client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentDisposition": f'inline; filename="{safe}"',
            },
            ExpiresIn=expires_seconds,
        )
        return url


@lru_cache(maxsize=4)
def _s3_client(
    endpoint_url: str | None, access_key_id: str, secret_access_key: str, region: str
) -> Any:
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name=region,
        config=Config(
            signature_version="s3v4",
            connect_timeout=10,
            read_timeout=30,
            retries={"max_attempts": 2},
        ),
    )


class LocalObjectStore:
    """A folder on disk, for development only (Render's disk is not persistent)."""

    def __init__(self, root: str) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        _check_key(key)
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError(f"unsafe storage key: {key!r}")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def list_objects(self, prefix: str) -> list[StoredObject]:
        _check_key(prefix)
        found: list[StoredObject] = []
        for path in self.root.rglob("*"):
            if path.is_file():
                key = path.relative_to(self.root).as_posix()
                if key.startswith(prefix):
                    found.append(
                        StoredObject(key, datetime.fromtimestamp(path.stat().st_mtime, UTC))
                    )
        return found

    def presigned_get_url(self, key: str, *, filename: str, expires_seconds: int) -> str | None:
        return None  # the API serves the bytes itself


class InMemoryObjectStore:
    """For tests."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.modified: dict[str, datetime] = {}

    def put(self, key: str, data: bytes, content_type: str) -> None:
        _check_key(key)
        self.objects[key] = (data, content_type)
        self.modified[key] = datetime.now(UTC)

    def list_objects(self, prefix: str) -> list[StoredObject]:
        return [
            StoredObject(key, self.modified.get(key, datetime.now(UTC)))
            for key in self.objects
            if key.startswith(prefix)
        ]

    def get(self, key: str) -> bytes:
        return self.objects[key][0]

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def presigned_get_url(self, key: str, *, filename: str, expires_seconds: int) -> str | None:
        return None


class DisabledObjectStore:
    def put(self, key: str, data: bytes, content_type: str) -> None:
        raise StorageDisabled()

    def get(self, key: str) -> bytes:
        raise StorageDisabled()

    def delete(self, key: str) -> None:
        logger.warning("object_store_disabled_delete", extra={"key": key})

    def list_objects(self, prefix: str) -> list[StoredObject]:
        return []

    def presigned_get_url(self, key: str, *, filename: str, expires_seconds: int) -> str | None:
        return None
