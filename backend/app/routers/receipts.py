"""Receipt upload router: object storage + OCR candidate extraction."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.category import Category
from app.models.user import User
from app.routers._scoping import visible_user_ids
from app.schemas.receipt import ReceiptCandidateRead
from app.services.minio import MinioReceiptStorage, ReceiptStorageError, get_receipt_storage
from app.services.ocr import ReceiptOcrError, ReceiptOcrService, ReceiptOcrUnavailableError

router = APIRouter(prefix="/api/receipts", tags=["receipts"])

MAX_RECEIPT_BYTES = 5 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "text/plain",
}


def get_receipt_ocr_service() -> ReceiptOcrService:
    return ReceiptOcrService()


def _visible_categories(db: Session, current_user: User) -> Sequence[Category]:
    user_ids = visible_user_ids(current_user)
    return (
        db.execute(
            select(Category).where(or_(Category.user_id.in_(user_ids), Category.user_id.is_(None))),
        )
        .scalars()
        .all()
    )


@router.post("/upload", response_model=ReceiptCandidateRead)
async def upload_receipt(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: MinioReceiptStorage = Depends(get_receipt_storage),
    ocr: ReceiptOcrService = Depends(get_receipt_ocr_service),
) -> ReceiptCandidateRead:
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Yalnızca JPG, PNG veya WEBP fiş görselleri yüklenebilir.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fiş dosyası boş görünüyor.",
        )
    if len(content) > MAX_RECEIPT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Fiş dosyası en fazla 5 MB olmalı.",
        )

    try:
        stored = storage.save_receipt(
            user_id=current_user.id,
            filename=file.filename or "receipt",
            content=content,
            content_type=content_type,
        )
    except ReceiptStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fiş görseli saklanamadı, biraz sonra tekrar dener misin?",
        ) from exc

    try:
        return ocr.analyze(
            content=content,
            content_type=content_type,
            filename=file.filename or "receipt",
            receipt_image_url=stored.public_url,
            categories=_visible_categories(db, current_user),
        )
    except ReceiptOcrUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OCR servisi hazır değil. Gemini veya OpenRouter anahtarını kontrol eder misin?",
        ) from exc
    except ReceiptOcrError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Fiş okunamadı. Daha net bir fotoğrafla tekrar dener misin?",
        ) from exc
