"""Private object storage for generated finance reports."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from minio import Minio
from minio.error import S3Error

from app.config import Settings, get_settings


class ReportStorageError(RuntimeError):
    """Raised when a generated report cannot be stored or fetched."""


@dataclass(frozen=True)
class StoredReport:
    object_name: str
    content_type: str
    file_size_bytes: int


class MinioReportStorage:
    """Store generated reports in a private MinIO bucket."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = Minio(
            endpoint=self._settings.minio_endpoint,
            access_key=self._settings.minio_root_user,
            secret_key=self._settings.minio_root_password,
            secure=self._settings.minio_use_ssl,
            region=self._settings.minio_region,
        )

    def save_report(
        self,
        *,
        user_id: UUID,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> StoredReport:
        bucket = self._settings.minio_bucket_reports
        object_name = self._object_name(user_id=user_id, filename=filename)
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
            raise ReportStorageError("Rapor dosyası kaydedilemedi.") from exc
        return StoredReport(
            object_name=object_name,
            content_type=content_type,
            file_size_bytes=len(content),
        )

    def read_report(self, object_name: str) -> bytes:
        try:
            response = self._client.get_object(self._settings.minio_bucket_reports, object_name)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except S3Error as exc:
            raise ReportStorageError("Rapor dosyası okunamadı.") from exc

    @staticmethod
    def _object_name(*, user_id: UUID, filename: str) -> str:
        suffix = PurePosixPath(filename).suffix.lower()
        if suffix not in {".docx", ".pdf"}:
            suffix = ".bin"
        return f"reports/{user_id}/{uuid4()}{suffix}"


def get_report_storage() -> MinioReportStorage:
    return MinioReportStorage(get_settings())
