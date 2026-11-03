import os

os.environ.setdefault("BASEROW_URL", "http://example.invalid")
os.environ.setdefault("BASEROW_API_TOKEN", "test")
os.environ.setdefault("APP_USERNAME", "test")
os.environ.setdefault("APP_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET", "test")

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.auth.deps import require_auth
from app.baserow import field_ids as f
from app.baserow.client import baserow_client
from app.main import app
from app.photos import MAX_DIMENSION, PhotoError, to_webp


def _jpeg(width: int, height: int, orientation: int | None = None) -> bytes:
    image = Image.new("RGB", (width, height), (200, 30, 30))
    out = BytesIO()
    if orientation:
        exif = Image.Exif()
        exif[0x0112] = orientation
        image.save(out, format="JPEG", exif=exif)
    else:
        image.save(out, format="JPEG")
    return out.getvalue()


def test_to_webp_resizes_and_converts():
    result = Image.open(BytesIO(to_webp(_jpeg(4000, 3000))))
    assert result.format == "WEBP"
    assert max(result.size) == MAX_DIMENSION
    assert result.size == (1600, 1200)


def test_to_webp_applies_exif_rotation():
    # Orientation 6 = rotate 90 degrees, so a landscape-stored photo is really portrait.
    result = Image.open(BytesIO(to_webp(_jpeg(800, 600, orientation=6))))
    assert result.size == (600, 800)


def test_to_webp_keeps_small_images_small():
    result = Image.open(BytesIO(to_webp(_jpeg(300, 400))))
    assert result.size == (300, 400)


def test_to_webp_rejects_non_images():
    with pytest.raises(PhotoError):
        to_webp(b"definitely not an image")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(f, "C_PHOTO", "field_photo")
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_upload_photo_stores_webp(client, monkeypatch):
    uploaded = {}

    async def fake_upload(filename, content, content_type):
        uploaded.update(filename=filename, content=content, content_type=content_type)
        return {"name": "abc.webp"}

    async def fake_update(table_id, row_id, values):
        uploaded["values"] = values
        return {"id": row_id, "field_photo": [{"name": "abc.webp", "url": "http://baserow/media/abc.webp"}]}

    monkeypatch.setattr(baserow_client, "upload_file", fake_upload)
    monkeypatch.setattr(baserow_client, "update_row", fake_update)

    resp = client.put("/api/copies/7/photo", files={"file": ("case.jpg", _jpeg(2000, 2600), "image/jpeg")})

    assert resp.status_code == 200
    assert resp.json()["photo_url"] == "http://baserow/media/abc.webp"
    assert uploaded["content_type"] == "image/webp"
    assert Image.open(BytesIO(uploaded["content"])).format == "WEBP"
    assert uploaded["values"] == {"field_photo": [{"name": "abc.webp"}]}


def test_upload_photo_rejects_garbage(client):
    resp = client.put("/api/copies/7/photo", files={"file": ("case.jpg", b"nope", "image/jpeg")})
    assert resp.status_code == 400


def test_upload_photo_requires_configured_field(client, monkeypatch):
    monkeypatch.setattr(f, "C_PHOTO", None)
    resp = client.put("/api/copies/7/photo", files={"file": ("case.jpg", _jpeg(10, 10), "image/jpeg")})
    assert resp.status_code == 400
