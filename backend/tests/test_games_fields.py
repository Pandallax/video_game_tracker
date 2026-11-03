import os

os.environ.setdefault("BASEROW_URL", "http://example.invalid")
os.environ.setdefault("BASEROW_API_TOKEN", "test")
os.environ.setdefault("APP_USERNAME", "test")
os.environ.setdefault("APP_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET", "test")

from datetime import date

import pytest
from fastapi import HTTPException

from app.baserow import field_ids as f
from app.routes import games
from app.schemas import GamePrices, game_row_to_out


def test_price_change_stamps_price_updated(monkeypatch):
    monkeypatch.setattr(f, "G_PRICE_UPDATED", "field_price_updated")
    values: dict = {}
    games._set_prices(values, GamePrices(cib=12.5))
    assert values == {f.G_CIB_PRICE: 12.5, "field_price_updated": date.today().isoformat()}


def test_price_clear_without_price_updated_field(monkeypatch):
    monkeypatch.setattr(f, "G_PRICE_UPDATED", None)
    values: dict = {}
    games._set_prices(values, GamePrices(cib=None))
    assert values == {f.G_CIB_PRICE: None}


def test_only_sent_price_kinds_are_written(monkeypatch):
    monkeypatch.setattr(f, "G_PRICE_UPDATED", None)
    monkeypatch.setattr(f, "G_LOOSE_PRICE", "field_loose")
    monkeypatch.setattr(f, "G_SEALED_PRICE", "field_sealed")
    values: dict = {}
    games._set_prices(values, GamePrices.model_validate({"loose": 4.0, "sealed": None}))
    assert values == {"field_loose": 4.0, "field_sealed": None}


def test_no_prices_sent_changes_nothing(monkeypatch):
    monkeypatch.setattr(f, "G_PRICE_UPDATED", "field_price_updated")
    values: dict = {}
    games._set_prices(values, GamePrices())
    assert values == {}


def test_unconfigured_price_kind_is_rejected(monkeypatch):
    monkeypatch.setattr(f, "G_BOX_ONLY_PRICE", None)
    with pytest.raises(HTTPException) as exc:
        games._set_prices({}, GamePrices(box_only=3.0))
    assert exc.value.status_code == 400
    assert "box_only" in exc.value.detail


def test_game_row_reads_prices(monkeypatch):
    monkeypatch.setattr(f, "G_LOOSE_PRICE", "field_loose")
    monkeypatch.setattr(f, "G_SEALED_PRICE", "field_sealed")
    monkeypatch.setattr(f, "G_BOX_ONLY_PRICE", None)
    monkeypatch.setattr(f, "G_MANUAL_ONLY_PRICE", None)
    row = {"id": 1, f.G_TITLE: "Halo", "field_loose": "5.25", f.G_CIB_PRICE: "12.00", "field_sealed": None}
    game = game_row_to_out(row)
    assert game.prices == GamePrices(loose=5.25, cib=12.0)
    assert game.price_kinds == ["loose", "cib", "sealed"]


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
