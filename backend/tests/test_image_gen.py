"""Tests for educational concept illustration storage."""

from __future__ import annotations

import json
from io import BytesIO
from uuid import uuid4

from pytest import MonkeyPatch

from app.config import Settings
from app.services import image_gen
from app.services.image_gen import IllustrationService


class FakeMinio:
    instances: list[FakeMinio] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.policies: list[tuple[str, str]] = []
        self.objects: list[tuple[str, str, bytes, str]] = []
        FakeMinio.instances.append(self)

    def bucket_exists(self, bucket: str) -> bool:
        return True

    def make_bucket(self, bucket: str, location: str | None = None) -> None:
        raise AssertionError("Existing bucket should not be recreated")

    def set_bucket_policy(self, bucket: str, policy: str) -> None:
        self.policies.append((bucket, policy))

    def put_object(
        self,
        bucket: str,
        object_name: str,
        data: BytesIO,
        *,
        length: int,
        content_type: str,
    ) -> None:
        self.objects.append((bucket, object_name, data.read(length), content_type))


def test_illustration_bucket_policy_allows_public_reads(monkeypatch: MonkeyPatch) -> None:
    FakeMinio.instances.clear()
    monkeypatch.setattr(image_gen, "Minio", FakeMinio)
    monkeypatch.setattr(
        IllustrationService,
        "_call_openrouter",
        lambda self, *, prompt: (b"fake-image", "image/jpeg"),
    )
    settings = Settings(
        app_env="test",
        jwt_secret="test-secret-test-secret-test-secret",
        llm_provider="openrouter",
        openrouter_api_key="test-key",
        minio_endpoint="localhost:9000",
        minio_public_endpoint="http://localhost:9000",
        minio_root_user="minioadmin",
        minio_root_password="minioadmin",
        minio_bucket_illustrations="illustrations",
    )

    illustration = IllustrationService(settings).illustrate(
        user_id=uuid4(),
        concept="faiz",
        audience="child",
    )

    client = FakeMinio.instances[-1]
    assert illustration.public_url.startswith("http://localhost:9000/illustrations/")
    assert client.objects[0][0] == "illustrations"
    assert client.objects[0][2] == b"fake-image"
    assert client.policies

    bucket, policy_text = client.policies[0]
    policy = json.loads(policy_text)
    statement = policy["Statement"][0]
    assert bucket == "illustrations"
    assert statement["Effect"] == "Allow"
    assert statement["Principal"] == {"AWS": ["*"]}
    assert statement["Action"] == ["s3:GetObject"]
    assert statement["Resource"] == ["arn:aws:s3:::illustrations/*"]
