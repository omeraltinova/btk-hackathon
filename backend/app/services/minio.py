"""Receipt object storage backed by MinIO."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from minio import Minio
from minio.error import S3Error

from app.config import Settings, get_settings


class ReceiptStorageError(RuntimeError):
    """Raised when the receipt image cannot be stored."""


@dataclass(frozen=True)
class StoredReceipt:
    object_name: str
    public_url: str


class MinioReceiptStorage:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_root_user,
            secret_key=settings.minio_root_password,
            secure=settings.minio_use_ssl,
            region=settings.minio_region,
        )

    def save_receipt(
        self,
        *,
        user_id: UUID,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> StoredReceipt:
        object_name = self._object_name(user_id=user_id, filename=filename)
        bucket = self._settings.minio_bucket_receipts
        try:
            if not self._client.bucket_exists(bucket):
                self._client.make_bucket(bucket, location=self._settings.minio_region)
            self._client.put_object(
                bucket,
                object_name,
                BytesIO(content),
                length=len(content),
                content_type=content_type,
            )
        except S3Error as exc:
            raise ReceiptStorageError("Receipt image storage failed.") from exc

        public_base = self._settings.minio_public_endpoint.rstrip("/")
        return StoredReceipt(
            object_name=object_name,
            public_url=f"{public_base}/{bucket}/{object_name}",
        )

    @staticmethod
    def _object_name(*, user_id: UUID, filename: str) -> str:
        suffix = PurePosixPath(filename).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".txt"}:
            suffix = ".bin"
        return f"receipts/{user_id}/{uuid4()}{suffix}"


def get_receipt_storage() -> MinioReceiptStorage:
    return MinioReceiptStorage(get_settings())
