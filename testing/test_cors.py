"""CORS: which browser origins may call the API (preflight through the real app)."""

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main as main_module


def _preflight(origin: str) -> httpx.Response:
    async def send():
        transport = httpx.ASGITransport(app=main_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as client:
            return await client.options(
                "/health",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "content-type",
                },
            )

    return asyncio.run(send())


@pytest.mark.parametrize("origin", [
    "https://query-mind-tawny.vercel.app",
    "https://query-mind-abc123xyz-raghavoids-projects.vercel.app",
    "https://query-mind-git-main-raghavoid.vercel.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:4173",
])
def test_frontend_origins_are_allowed(origin):
    response = _preflight(origin)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


@pytest.mark.parametrize("origin", [
    "https://evil.example.com",
    "https://query-mind-tawny.vercel.app.evil.com",
    "https://notquery-mind.vercel.app",
    "http://query-mind-tawny.vercel.app",
])
def test_other_origins_are_refused(origin):
    response = _preflight(origin)
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
