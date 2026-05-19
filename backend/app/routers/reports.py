"""Generated report download endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.generated_report import GeneratedReport
from app.models.user import User
from app.services.report_storage import MinioReportStorage, ReportStorageError

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _report_or_404(db: Session, current_user: User, report_id: UUID) -> GeneratedReport:
    report = db.execute(
        select(GeneratedReport).where(
            GeneratedReport.id == report_id,
            GeneratedReport.user_id == current_user.id,
        ),
    ).scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rapor bulunamadı.")
    return report


@router.get("/{report_id}/download")
def download_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Download a private generated report owned by the current profile."""
    report = _report_or_404(db, current_user, report_id)
    try:
        content = MinioReportStorage().read_report(report.object_name)
    except ReportStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rapor dosyası şu an indirilemedi.",
        ) from exc
    metadata = report.metadata_json or {}
    filename = metadata.get("filename") if isinstance(metadata.get("filename"), str) else None
    if filename is None:
        filename = f"cuzdan-kocu-raporu.{report.format}"
    return Response(
        content=content,
        media_type=report.content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
