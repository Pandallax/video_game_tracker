import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import import_completionator as ic  # noqa: E402


def row(title_href, title, edition="", loose="$5.00", complete="$9.50", new="$1,050.00", img_src="x.jpg"):
    return (
        f'<td><a href="{title_href}"><img src="{img_src}"></a></td>'
        f'<td><a href="{title_href}">{title}</a></td>'
        f"<td>{edition}</td><td>First-person Shooter</td>"
        f"<td>{loose}</td><td>{complete}</td><td>{new}</td>"
        "<td>Official Release</td><td>11/15/2001</td><td>90 %</td><td>3.0</td><td>None</td>"
    )


SAMPLE_ROWS = [
    row("/Game/Details/1", "Halo: Combat Evolved"),
    row("/Game/Details/1", "Halo: Combat Evolved", edition="Platinum Hits", complete="", img_src=""),
    row("/Game/Details/2", "Tom Clancy&#39;s Splinter Cell", loose="$3.00", complete="$6.00", new="$15.00"),
    row("/Game/Details/3", "Brand New Game", loose="$1.00", complete="$2.00", new="$3.00"),
]


def test_parse_rows():
    entries = ic.parse_rows(SAMPLE_ROWS)
    assert [e.baserow_title for e in entries] == [
        "Halo: Combat Evolved",
        "Halo: Combat Evolved (Platinum Hits)",
        "Tom Clancy's Splinter Cell",
        "Brand New Game",
    ]
    halo, halo_ph = entries[0], entries[1]
    assert (halo.loose, halo.complete, halo.new) == (5.0, 9.5, 1050.0)
    assert halo.url == "https://www.completionator.com/Game/Details/1"
    assert halo.cover_url == "x.jpg"
    assert halo_ph.edition == "Platinum Hits"
    assert halo_ph.complete is None
    assert halo_ph.cover_url == ""


def test_compare_buckets():
    entries = ic.parse_rows(SAMPLE_ROWS)
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


def test_parse_row_skips_malformed():
    assert ic.parse_row("<td>not enough cells</td>") is None
