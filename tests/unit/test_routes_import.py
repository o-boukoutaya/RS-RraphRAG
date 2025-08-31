from __future__ import annotations
import io
import pytest
from httpx import AsyncClient
from app.main import app
from app.core import config as cfgmod

@pytest.mark.asyncio
async def test_import_route_ok():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        files = [
            ("files", ("doc1.txt", io.BytesIO(b"Hello"), "text/plain")),
            ("files", ("doc2.txt", io.BytesIO(b"World"), "text/plain")),
        ]
        r = await ac.post("/api/corpus/import", params={"series": "s1"}, files=files)
        assert r.status_code == 200
        data = r.json()
        assert data["series"] == "s1"
        assert len(data["accepted"]) == 2