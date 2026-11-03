import os

os.environ.setdefault("BASEROW_URL", "http://example.invalid")
os.environ.setdefault("BASEROW_API_TOKEN", "test")
os.environ.setdefault("APP_USERNAME", "test")
os.environ.setdefault("APP_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET", "test")

from datetime import date

from app.baserow import field_ids as f
from app.routes import games
from app.schemas import game_row_to_out


def test_market_price_change_stamps_price_updated(monkeypatch):
    monkeypatch.setattr(f, "G_PRICE_UPDATED", "field_price_updated")
    values: dict = {}
    games._set_market_price(values, 12.5)
    assert values == {f.G_MARKET_PRICE: 12.5, "field_price_updated": date.today().isoformat()}


def test_market_price_without_price_updated_field(monkeypatch):
    monkeypatch.setattr(f, "G_PRICE_UPDATED", None)
    values: dict = {}
    games._set_market_price(values, None)
    assert values == {f.G_MARKET_PRICE: None}


def test_game_row_reads_optional_fields(monkeypatch):
    monkeypatch.setattr(f, "G_COVER_URL", "field_cover")
    monkeypatch.setattr(f, "G_PRICE_UPDATED", "field_price_updated")
    row = {
        "id": 1,
        f.G_TITLE: "Halo",
        "field_cover": "https://example.com/halo.jpg",
        "field_price_updated": "2026-11-03",
    }
    game = game_row_to_out(row)
    assert game.cover_url == "https://example.com/halo.jpg"
    assert game.price_updated == "2026-11-03"


def test_game_row_without_optional_fields(monkeypatch):
    monkeypatch.setattr(f, "G_COVER_URL", None)
    monkeypatch.setattr(f, "G_PRICE_UPDATED", None)
    game = game_row_to_out({"id": 1, f.G_TITLE: "Halo"})
    assert game.cover_url is None
    assert game.price_updated is None
