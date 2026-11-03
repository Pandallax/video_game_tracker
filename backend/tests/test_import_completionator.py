import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import import_completionator as ic  # noqa: E402

SAMPLE = (Path(__file__).parent / "fixtures" / "completionator_sample.htm").read_text()


def test_parse_checklist_rows():
    entries = ic.parse_checklist(SAMPLE)
    assert [e.baserow_title for e in entries] == [
        "Halo: Combat Evolved",
        "Halo: Combat Evolved (Platinum Hits)",
        "Tom Clancy's Splinter Cell",
        "Brand New Game",
    ]
    halo, halo_ph = entries[0], entries[1]
    assert (halo.loose, halo.complete, halo.new) == (5.0, 9.5, 1050.0)
    assert halo.url == "https://www.completionator.com/Game/Details/1"
    assert halo_ph.edition == "Platinum Hits"
    assert halo_ph.complete is None


def test_compare_buckets():
    entries = ic.parse_checklist(SAMPLE)
    games = [
        (10, "Halo: Combat Evolved"),
        (11, "Tom Clancys Splinter Cell"),  # punctuation-only difference -> exact after normalizing
        (12, "Brand New Gamez"),  # close but not exact -> possible match
        (13, "Only In Baserow"),
    ]
    c = ic.compare(entries, games)
    assert {(e.baserow_title, rid) for e, rid in c.matched} == {
        ("Halo: Combat Evolved", 10),
        ("Tom Clancy's Splinter Cell", 11),
    }
    assert [(e.title, rid) for e, rid, _, _ in c.possible] == [("Brand New Game", 12)]
    assert [e.baserow_title for e in c.missing] == ["Halo: Combat Evolved (Platinum Hits)"]
    assert c.only_in_baserow == [(13, "Only In Baserow")]


def test_parse_rejects_other_pages():
    import pytest

    with pytest.raises(ValueError):
        ic.parse_checklist("<html><body><p>nope</p></body></html>")
