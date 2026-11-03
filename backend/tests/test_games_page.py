import os

os.environ.setdefault("BASEROW_URL", "http://example.invalid")
os.environ.setdefault("BASEROW_API_TOKEN", "test")
os.environ.setdefault("APP_USERNAME", "test")
os.environ.setdefault("APP_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET", "test")

import asyncio

import pytest
from fastapi import HTTPException

from app.baserow import field_ids as f
from app.baserow.client import BaserowClient
from app.routes import games


def test_search_params_default_sorts_by_title():
    assert games.search_params() == {"order_by": f.G_TITLE}


def test_search_params_title_and_platform():
    params = games.search_params("  halo ", "OG Xbox")
    assert params[f"filter__{f.G_TITLE}__contains"] == "halo"
    assert params[f"filter__{f.G_PLATFORM}__single_select_equal"] == str(f.PLATFORM_OPTIONS["OG Xbox"])


def test_search_params_digits_search_upc():
    params = games.search_params("0 12345-67890")
    assert params[f"filter__{f.G_UPC}__contains"] == "1234567890"
    assert f"filter__{f.G_TITLE}__contains" not in params


def test_search_params_short_number_is_a_title():
    # "007" or "2" should still find titles like "007: Agent Under Fire".
    assert games.search_params("007")[f"filter__{f.G_TITLE}__contains"] == "007"


def test_search_params_unknown_platform():
    with pytest.raises(HTTPException):
        games.search_params("", "Dreamcast")


def test_list_rows_fetches_remaining_pages(monkeypatch):
    calls = []

    async def fake_page(self, table_id, *, page=1, size=200, params=None, client=None):
        calls.append(page)
        total = 450
        start = (page - 1) * size
        return [{"id": i} for i in range(start, min(start + size, total))], total

    monkeypatch.setattr(BaserowClient, "list_rows_page", fake_page)
    rows = asyncio.run(BaserowClient().list_rows(f.TABLE_GAMES))
    assert len(rows) == 450
    assert [r["id"] for r in rows] == list(range(450))
    assert sorted(calls) == [1, 2, 3]


def test_games_page_endpoint(monkeypatch):
    seen = {}

    async def fake_page(table_id, *, page, size, params):
        seen.update(page=page, size=size, params=params)
        return [{"id": 1, f.G_TITLE: "Halo"}], 37

    async def fake_edition_key():
        return None

    monkeypatch.setattr(games.baserow_client, "list_rows_page", fake_page)
    monkeypatch.setattr(games, "_edition_key", fake_edition_key)
    result = asyncio.run(games.list_games_page(search="halo", platform=None, page=2, size=10))
    assert result.total == 37 and result.page == 2 and [g.title for g in result.items] == ["Halo"]
    assert seen["page"] == 2 and seen["size"] == 10
    assert seen["params"][f"filter__{f.G_TITLE}__contains"] == "halo"
