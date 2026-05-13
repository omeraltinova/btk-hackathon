"""Educational illustration generator backed by Gemini's image-capable model.

This service is **only** used by the `illustrate_concept` agent tool to draw a
concept (faiz, kumbara, enflasyon, etc.) for the coach mode. Per P7/A-4 it is
NOT for investment, product, or price suggestions — the tool prompt and the
calling site both enforce this.

Failure modes (missing key, provider error, safety block, network error) all
raise `IllustrationUnavailableError` with a Turkish user-facing detail; the
chat runner converts that to a graceful inline message and never reveals raw
provider errors to the user.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import unicodedata
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from uuid import UUID, uuid4

import httpx
from minio import Minio
from minio.error import S3Error

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

GEMINI_IMAGE_MODEL_DEFAULT = "gemini-2.5-flash-image-preview"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class IllustrationUnavailableError(RuntimeError):
    """Raised when the illustration cannot be generated or stored."""


@dataclass(frozen=True)
class Illustration:
    object_name: str
    public_url: str
    prompt: str
    concept: str


class IllustrationService:
    """Generate a single educational illustration and persist it to MinIO."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = Minio(
            endpoint=self._settings.minio_endpoint,
            access_key=self._settings.minio_root_user,
            secret_key=self._settings.minio_root_password,
            secure=self._settings.minio_use_ssl,
            region=self._settings.minio_region,
        )

    def illustrate(self, *, user_id: UUID, concept: str, audience: str) -> Illustration:
        if not self._settings.gemini_api_key:
            raise IllustrationUnavailableError(
                "Görsel anlatım servisi şu an hazır değil.",
            )
        prompt = self._build_prompt(concept=concept, audience=audience)
        image_bytes, content_type = self._call_gemini(prompt=prompt)
        stored = self._store(
            user_id=user_id,
            content=image_bytes,
            content_type=content_type,
        )
        return Illustration(
            object_name=stored,
            public_url=self._public_url(stored),
            prompt=prompt,
            concept=concept,
        )

    def _ascii_header(self, raw: str | None) -> str | None:
        if raw is None:
            return None
        normalized = unicodedata.normalize("NFKD", raw)
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii").strip()
        return ascii_text or None

    def _build_prompt(self, *, concept: str, audience: str) -> str:
        normalized_concept = " ".join(concept.split()) or "finansal kavram"
        child_hint = (
            "for a Turkish child (ages 6-12), warm cartoon style, pastel palette, "
            "include familiar Turkish childhood objects like a kumbara (piggy bank), "
            "harçlık coins, an okul çantası or a bayram envelope when appropriate"
            if audience == "child"
            else "warm, friendly editorial illustration style, soft pastels, "
            "Turkish family-finance setting, no charts, no text in the image"
        )
        # Explicit safety constraints aligned with master plan P7 / A-4: no
        # product names, no investment advice imagery, no real brand logos.
        return (
            "Create a single illustration that visually explains the Turkish personal-finance "
            f"concept '{normalized_concept}'. Style: {child_hint}. "
            "Constraints: no text or numbers in the image, no charts or graphs, "
            "no brand logos, no specific product names, no realistic currency symbols. "
            "Friendly, non-judgmental, educational. Square aspect."
        )

    def _call_gemini(self, *, prompt: str) -> tuple[bytes, str]:
        model = self._settings.gemini_image_model or GEMINI_IMAGE_MODEL_DEFAULT
        url = f"{GEMINI_BASE_URL}/{model}:generateContent"
        body: dict[str, object] = {
            "contents": [
                {"role": "user", "parts": [{"text": prompt}]},
            ],
            "generationConfig": {
                "responseModalities": ["IMAGE", "TEXT"],
                "temperature": 0.7,
            },
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._settings.gemini_api_key or "",
        }
        try:
            response = httpx.post(url, headers=headers, json=body, timeout=60.0)
        except httpx.HTTPError as exc:
            logger.warning("illustration_provider_error: %s", type(exc).__name__)
            raise IllustrationUnavailableError(
                "Görsel anlatım servisi şu an cevap vermedi.",
            ) from exc

        if response.status_code >= 400:
            logger.warning("illustration_provider_http_error: status=%s", response.status_code)
            raise IllustrationUnavailableError(
                "Görsel anlatım servisi şu an cevap vermedi.",
            )

        try:
            payload: dict[str, object] = response.json()
        except json.JSONDecodeError as exc:
            raise IllustrationUnavailableError(
                "Görsel anlatım yanıtı okunamadı.",
            ) from exc

        candidates_raw = payload.get("candidates")
        if not isinstance(candidates_raw, list):
            raise IllustrationUnavailableError("Görsel anlatım yanıtı boş geldi.")
        for candidate in candidates_raw:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content")
            if not isinstance(content, dict):
                continue
            parts = content.get("parts")
            if not isinstance(parts, list):
                continue
            for part in parts:
                if not isinstance(part, dict):
                    continue
                inline = part.get("inline_data") or part.get("inlineData")
                if not isinstance(inline, dict):
                    continue
                data_b64 = inline.get("data")
                mime = inline.get("mime_type") or inline.get("mimeType") or "image/png"
                if not isinstance(data_b64, str) or not isinstance(mime, str):
                    continue
                try:
                    return base64.b64decode(data_b64, validate=True), mime
                except (binascii.Error, ValueError) as exc:
                    raise IllustrationUnavailableError(
                        "Görsel anlatım verisi çözülemedi.",
                    ) from exc
        raise IllustrationUnavailableError(
            "Görsel anlatım servisi şu an görsel üretmedi.",
        )

    def _store(self, *, user_id: UUID, content: bytes, content_type: str) -> str:
        bucket = self._settings.minio_bucket_illustrations
        suffix = self._suffix_for(content_type)
        object_name = f"illustrations/{user_id}/{uuid4()}{suffix}"
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
            raise IllustrationUnavailableError("Görsel kaydedilemedi.") from exc
        return object_name

    def _public_url(self, object_name: str) -> str:
        base = self._settings.minio_public_endpoint.rstrip("/")
        return f"{base}/{self._settings.minio_bucket_illustrations}/{object_name}"

    @staticmethod
    def _suffix_for(content_type: str) -> str:
        suffix = PurePosixPath(content_type.replace("/", ".")).suffix.lower()
        if suffix in {".png", ".jpeg", ".jpg", ".webp"}:
            return ".png" if suffix == ".png" else suffix
        return ".png"
