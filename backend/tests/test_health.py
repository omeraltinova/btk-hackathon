"""Smoke test for the /health endpoint. Day 1 only — no DB required."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_day_7_chat_support_routes_are_registered() -> None:
    paths = {getattr(route, "path", "") for route in app.routes}

    assert "/api/conversations" in paths
    assert "/api/conversations/{conversation_id}" in paths
    assert "/api/conversations/{conversation_id}/messages" in paths
    assert "/api/memory" in paths
    assert "/api/memory/{key}" in paths
