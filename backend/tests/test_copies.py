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
from app.routes import copies
from app.schemas import CopyCreate, CopyUpdate, copy_row_to_out, needs_condition

COLLECTION = {"id": f.STATUS_OPTIONS["Collection"], "value": "Collection"}


def test_next_copy_id_continues_series():
    assert copies.next_copy_id([]) == "C-0001"
    assert copies.next_copy_id(["C-0009", "C-0041", "junk", ""]) == "C-0042"
    assert copies.next_copy_id(["OGX-7", "OGX-12"]) == "OGX-13"
    assert copies.next_copy_id(["X-099"]) == "X-100"


def test_default_status():
    rows = [{f.C_GAME: [{"id": 5}], f.C_STATUS: COLLECTION}]
    assert copies.default_status(5, rows) == "For Sale"
    assert copies.default_status(6, rows) == "Collection"


def test_needs_condition():
    assert needs_condition(True, ((False, None),) * 3) is False  # sealed
    assert needs_condition(False, ((False, None),) * 3) is True  # no parts recorded
    assert needs_condition(False, ((True, 8), (True, None), (False, None))) is True  # case ungraded
    assert needs_condition(False, ((True, 8), (True, 7), (False, None))) is False


def test_copy_out_flags():
    out = copy_row_to_out({"id": 1, f.C_HAS_DISC: True, f.C_DISC_QUALITY: 9}, platform="OG Xbox")
    assert out.needs_price and not out.needs_condition and out.platform == "OG Xbox"
    out = copy_row_to_out({"id": 1, f.C_PURCHASE_PRICE: "4.00"})
    assert not out.needs_price and out.needs_condition


def test_update_values_clears_and_unchecks():
    v = copies.update_values(CopyUpdate.model_validate({"purchase_price": None, "has_case": False, "disc_quality": 7}))
    assert v == {f.C_PURCHASE_PRICE: None, f.C_HAS_CASE: False, f.C_CASE_QUALITY: None, f.C_DISC_QUALITY: 7}
    assert copies.update_values(CopyUpdate()) == {}


def test_update_values_sealed_clears_parts():
    v = copies.update_values(CopyUpdate(sealed=True))
    assert v[f.C_SEALED] is True
    assert v[f.C_HAS_DISC] is False and v[f.C_DISC_QUALITY] is None and v[f.C_MANUAL_QUALITY] is None


def test_update_values_bad_status():
    with pytest.raises(HTTPException):
        copies.update_values(CopyUpdate(status="Lost"))


class FakeBaserow:
    def __init__(self, games, copy_rows):
        self.games = {g["id"]: g for g in games}
        self.copy_rows = copy_rows
        self.created = None

    async def get_row(self, table_id, row_id):
        return self.games.get(row_id)

    async def list_rows(self, table_id):
        return self.copy_rows if table_id == f.TABLE_COPIES else list(self.games.values())

    async def create_row(self, table_id, values):
        self.created = values
        return {"id": 99, **values, f.C_GAME: [{"id": values[f.C_GAME][0], "value": "x"}],
                f.C_STATUS: {"value": next(k for k, v in f.STATUS_OPTIONS.items() if v == values[f.C_STATUS])}}


def test_create_copy_auto_id_status_and_parts(monkeypatch):
    game = {"id": 5, f.G_TITLE: "Halo", f.G_PLATFORM: {"value": "OG Xbox"}, f.G_CIB_REQUIRES: []}
    fake = FakeBaserow([game], [{"id": 1, f.C_COPY_ID: "C-0007", f.C_GAME: [{"id": 5}], f.C_STATUS: COLLECTION}])
    monkeypatch.setattr(copies, "baserow_client", fake)
    body = CopyCreate(game_id=5, has_disc=True, disc_quality=8, has_case=False, case_quality=6)
    out = asyncio.run(copies.create_copy(body))
    assert fake.created[f.C_COPY_ID] == "C-0008"
    assert fake.created[f.C_STATUS] == f.STATUS_OPTIONS["For Sale"]  # already have one in the collection
    assert fake.created[f.C_CASE_QUALITY] is None  # no case -> no case quality
    assert out.platform == "OG Xbox" and out.needs_price


def test_create_copy_rejects_duplicate_id(monkeypatch):
    fake = FakeBaserow([{"id": 5}], [{"id": 1, f.C_COPY_ID: "C-0007"}])
    monkeypatch.setattr(copies, "baserow_client", fake)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(copies.create_copy(CopyCreate(game_id=5, copy_id="c-0007")))
    assert "already used" in exc.value.detail
