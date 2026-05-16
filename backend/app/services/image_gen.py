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

GEMINI_IMAGE_MODEL_DEFAULT = "gemini-3.1-flash-image-preview"
OPENROUTER_IMAGE_MODEL_DEFAULT = "google/gemini-3.1-flash-image-preview"
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
        prompt = self._build_prompt(concept=concept, audience=audience)
        if self._settings.llm_provider == "openrouter":
            if not self._settings.openrouter_api_key:
                raise IllustrationUnavailableError(
                    "Görsel anlatım servisi şu an hazır değil.",
                )
            image_bytes, content_type = self._call_openrouter(prompt=prompt)
        else:
            if not self._settings.gemini_api_key:
                raise IllustrationUnavailableError(
                    "Görsel anlatım servisi şu an hazır değil.",
                )
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

    def _call_openrouter(self, *, prompt: str) -> tuple[bytes, str]:
        model = self._settings.openrouter_image_model or OPENROUTER_IMAGE_MODEL_DEFAULT
        url = f"{self._settings.openrouter_base_url.rstrip('/')}/chat/completions"
        body: dict[str, object] = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}],
                },
            ],
            "modalities": ["image", "text"],
            "temperature": 0.7,
        }
        headers = {
            "Authorization": f"Bearer {self._settings.openrouter_api_key or ''}",
            "Content-Type": "application/json",
        }
        if self._settings.openrouter_http_referer:
            headers["HTTP-Referer"] = (
                self._ascii_header(
                    self._settings.openrouter_http_referer,
                )
                or "http://localhost:3000"
            )
        if self._settings.openrouter_app_title:
            headers["X-Title"] = (
                self._ascii_header(self._settings.openrouter_app_title) or "Cuzdan Kocu"
            )

        try:
            response = httpx.post(url, headers=headers, json=body, timeout=120.0)
        except httpx.HTTPError as exc:
            logger.warning("illustration_openrouter_error: %s", type(exc).__name__)
            raise IllustrationUnavailableError(
                "Görsel anlatım servisi şu an cevap vermedi.",
            ) from exc

        if response.status_code >= 400:
            logger.warning("illustration_openrouter_http_error: status=%s", response.status_code)
            raise IllustrationUnavailableError(
                "Görsel anlatım servisi şu an cevap vermedi.",
            )

        try:
            payload: dict[str, object] = response.json()
        except json.JSONDecodeError as exc:
            raise IllustrationUnavailableError(
                "Görsel anlatım yanıtı okunamadı.",
            ) from exc

        image = self._extract_openrouter_image(payload)
        if image is None:
            raise IllustrationUnavailableError(
                "Görsel anlatım servisi şu an görsel üretmedi.",
            )
        return image

    def _extract_openrouter_image(self, payload: dict[str, object]) -> tuple[bytes, str] | None:
        choices = payload.get("choices")
        if not isinstance(choices, list):
            return None
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if not isinstance(message, dict):
                continue
            image = self._extract_image_from_message(message)
            if image is not None:
                return image
        return None

    def _extract_image_from_message(self, message: dict[str, object]) -> tuple[bytes, str] | None:
        images = message.get("images")
        if isinstance(images, list):
            for image in images:
                extracted = self._extract_image_from_part(image)
                if extracted is not None:
                    return extracted

        content = message.get("content")
        if isinstance(content, list):
            for part in content:
                extracted = self._extract_image_from_part(part)
                if extracted is not None:
                    return extracted
        elif isinstance(content, dict):
            return self._extract_image_from_part(content)
        return None

    def _extract_image_from_part(self, part: object) -> tuple[bytes, str] | None:
        if not isinstance(part, dict):
            return None

        for key in ("image_url", "image", "inline_data", "inlineData"):
            nested = part.get(key)
            if isinstance(nested, str):
                extracted = self._image_from_reference(nested, default_mime="image/png")
                if extracted is not None:
                    return extracted
            if isinstance(nested, dict):
                url = nested.get("url")
                if isinstance(url, str):
                    extracted = self._image_from_reference(url, default_mime="image/png")
                    if extracted is not None:
                        return extracted
                data = nested.get("data") or nested.get("b64_json")
                mime = nested.get("mime_type") or nested.get("mimeType") or "image/png"
                if isinstance(data, str) and isinstance(mime, str):
                    extracted = self._image_from_reference(data, default_mime=mime)
                    if extracted is not None:
                        return extracted

        url = part.get("url")
        if isinstance(url, str):
            return self._image_from_reference(url, default_mime="image/png")
        data = part.get("data") or part.get("b64_json")
        if isinstance(data, str):
            return self._image_from_reference(data, default_mime="image/png")
        return None

    def _image_from_reference(
        self, reference: str, *, default_mime: str
    ) -> tuple[bytes, str] | None:
        if reference.startswith("data:"):
            header, separator, encoded = reference.partition(",")
            if not separator:
                return None
            mime = header.removeprefix("data:").split(";", 1)[0] or default_mime
            try:
                return base64.b64decode(encoded, validate=True), mime
            except (binascii.Error, ValueError):
                return None
        if reference.startswith("http://") or reference.startswith("https://"):
            try:
                response = httpx.get(reference, timeout=60.0)
                response.raise_for_status()
            except httpx.HTTPError:
                return None
            return response.content, response.headers.get("content-type", default_mime)
        try:
            return base64.b64decode(reference, validate=True), default_mime
        except (binascii.Error, ValueError):
            return None

    def _store(self, *, user_id: UUID, content: bytes, content_type: str) -> str:
        bucket = self._settings.minio_bucket_illustrations
        suffix = self._suffix_for(content_type)
        object_name = f"illustrations/{user_id}/{uuid4()}{suffix}"
        try:
            self._ensure_public_read_bucket(bucket)
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

    def _ensure_public_read_bucket(self, bucket: str) -> None:
        if not self._client.bucket_exists(bucket):
            self._client.make_bucket(bucket, location=self._settings.minio_region)
        # Illustration URLs are rendered directly in the browser chat stream.
        self._client.set_bucket_policy(
            bucket,
            json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": ["*"]},
                            "Action": ["s3:GetObject"],
                            "Resource": [f"arn:aws:s3:::{bucket}/*"],
                        },
                    ],
                },
            ),
        )

    def _public_url(self, object_name: str) -> str:
        base = self._settings.minio_public_endpoint.rstrip("/")
        return f"{base}/{self._settings.minio_bucket_illustrations}/{object_name}"

    @staticmethod
    def _suffix_for(content_type: str) -> str:
        suffix = PurePosixPath(content_type.replace("/", ".")).suffix.lower()
        if suffix in {".png", ".jpeg", ".jpg", ".webp"}:
            return ".png" if suffix == ".png" else suffix
        return ".png"
