import os

os.environ.setdefault("BASEROW_URL", "http://example.invalid")
os.environ.setdefault("BASEROW_API_TOKEN", "test")
os.environ.setdefault("APP_USERNAME", "test")
os.environ.setdefault("APP_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET", "test")

import pytest

from app.baserow import field_ids as f
from app.baserow.game_fields import EditionField, edition_write_value, find_edition_field
from app.schemas import edition_from_value, game_row_to_out

SINGLE = EditionField(key="field_99", type="single_select", options={"Platinum Hits": 501, "Classics": 502})


def test_find_edition_field_by_name():
    fields = [
        {"id": 1, "name": "Title", "type": "text"},
        {"id": 99, "name": "Editions", "type": "single_select",
         "select_options": [{"id": 501, "value": "Platinum Hits", "color": "light-gray"}]},
    ]
    assert find_edition_field(fields) == EditionField("field_99", "single_select", {"Platinum Hits": 501})


def test_find_edition_field_missing():
    assert find_edition_field([{"id": 1, "name": "Title", "type": "text"}]) is None


def test_write_single_select_case_insensitive():
    assert edition_write_value(SINGLE, "platinum hits") == 501


def test_write_blank_clears():
    assert edition_write_value(SINGLE, "") is None
    assert edition_write_value(EditionField("field_99", "multiple_select", {"Platinum Hits": 501}), "") == []


def test_write_multiple_select_and_text():
    assert edition_write_value(EditionField("field_99", "multiple_select", {"Platinum Hits": 501}), "Platinum Hits") == [501]
    assert edition_write_value(EditionField("field_99", "text"), " Platinum Hits ") == "Platinum Hits"


def test_write_unknown_option_raises():
    with pytest.raises(ValueError):
        edition_write_value(SINGLE, "Greatest Hits")


def test_edition_from_value_shapes():
    assert edition_from_value({"id": 501, "value": "Platinum Hits", "color": "light-gray"}) == "Platinum Hits"
    assert edition_from_value(None) == ""
    assert edition_from_value([{"id": 501, "value": "Platinum Hits"}]) == "Platinum Hits"
    assert edition_from_value("Classics") == "Classics"


def test_game_row_reads_edition():
    row = {"id": 1, f.G_TITLE: "Halo", "field_99": {"id": 501, "value": "Platinum Hits"}}
    assert game_row_to_out(row, "field_99").edition == "Platinum Hits"
    assert game_row_to_out(row).edition == ""
