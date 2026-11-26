import os

os.environ.setdefault("BASEROW_URL", "http://example.invalid")
os.environ.setdefault("BASEROW_API_TOKEN", "test")
os.environ.setdefault("APP_USERNAME", "test")
os.environ.setdefault("APP_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET", "test")

import asyncio

from app.baserow import field_ids as f
from app.pricecharting import Entry, ImportOptions, parse_page, parse_row, plan_updates, run_import

EDITIONS_FIELD = {"id": 99, "name": "Editions", "type": "single_select",
                  "select_options": [{"id": 501, "value": "Platinum Hits"}]}
FIELDS = [EDITIONS_FIELD]
X360 = {"id": f.PLATFORM_OPTIONS["Xbox 360"], "value": "Xbox 360"}


def entry(title, edition="", loose=5.0, cib=9.5, new=40.0, cover="https://storage.googleapis.com/images.pricecharting.com/x/60.jpg"):
    slug = title.lower().replace(" ", "-")
    return Entry(title=title, edition=edition, loose=loose, cib=cib, new=new,
                 url=f"https://www.pricecharting.com/game/xbox-360/{slug}", cover_url=cover)


def row_html(title, href, loose="$5.84", cib="$10.25", new="$220.50", img_src="https://x/60.jpg"):
    return f"""
    <tr id="product-1" data-product="1">
        <td class="image"><div><a href="{href}"><img class="photo" src="{img_src}" /></a></div></td>
        <td class="title"><a href="{href}">{title}</a></td>
        <td class="price numeric used_price">{f'<span class="js-price">{loose}</span>' if loose else ''}</td>
        <td class="price numeric cib_price">{f'<span class="js-price">{cib}</span>' if cib else ''}</td>
        <td class="price numeric new_price">{f'<span class="js-price">{new}</span>' if new else ''}</td>
    </tr>
    """


class FakeBaserow:
    def __init__(self, rows):
        self.rows = rows
        self.updated: list[dict] = []

    async def list_rows(self, table_id):
        return self.rows

    async def list_fields(self, table_id):
        return FIELDS

    async def batch_update_rows(self, table_id, items):
        self.updated.extend(items)
        return items


def test_parses_title_price_and_cover():
    e = parse_row(row_html("Halo 3", "/game/xbox-360/halo-3"))
    assert e.title == "Halo 3" and e.edition == ""
    assert e.loose == 5.84 and e.cib == 10.25 and e.new == 220.50
    assert e.url == "https://www.pricecharting.com/game/xbox-360/halo-3"
    assert e.cover_url == "https://x/60.jpg"


def test_edition_extracted_from_trailing_brackets():
    e = parse_row(row_html("Ace Combat 6 Fires of Liberation [Platinum Hits]", "/game/xbox-360/ace-combat-6"))
    assert e.title == "Ace Combat 6 Fires of Liberation"
    assert e.edition == "Platinum Hits"
    assert e.baserow_title == "Ace Combat 6 Fires of Liberation (Platinum Hits)"


def test_missing_price_cell_is_none():
    e = parse_row(row_html("Rare Game", "/game/xbox-360/rare-game", loose="", cib="", new=""))
    assert e.loose is None and e.cib is None and e.new is None


def test_parse_page_finds_next_cursor():
    html = "<table><tbody>" + row_html("Halo 3", "/game/xbox-360/halo-3") + """
        </tbody></table>
        <form method="POST" action="" class="next_page js-next-page">
            <input type="hidden" name="cursor" value="150" />
        </form>
    """
    entries, cursor = parse_page(html)
    assert len(entries) == 1 and cursor == "150"


def test_parse_page_last_page_has_no_cursor():
    html = "<table><tbody>" + row_html("Halo 3", "/game/xbox-360/halo-3") + "</tbody></table>"
    entries, cursor = parse_page(html)
    assert len(entries) == 1 and cursor is None


def test_plan_fills_only_empty_fields_by_default():
    rows = {1: {"id": 1, f.G_CIB_PRICE: "12.00", f.G_COVER_URL: "https://mine.example/halo.jpg"}}
    plan = plan_updates([(entry("Halo 3"), 1)], rows, FIELDS, ImportOptions(), "2026-11-25")
    u = plan.updates[1]
    assert u[f.G_LOOSE_PRICE] == 5.0 and u[f.G_SEALED_PRICE] == 40.0
    assert f.G_CIB_PRICE not in u  # already set
    assert f.G_COVER_URL not in u  # hand-entered cover kept
    assert u[f.G_PRICE_UPDATED] == "2026-11-25"
    assert plan.prices == 2 and plan.covers == 0


def test_plan_overwrite_and_unchanged_values():
    rows = {1: {"id": 1, f.G_CIB_PRICE: "9.50", f.G_LOOSE_PRICE: "4.00", f.G_COVER_URL: "old.jpg"}}
    opts = ImportOptions(overwrite_prices=True, overwrite_covers=True)
    plan = plan_updates([(entry("Halo 3"), 1)], rows, FIELDS, opts, "2026-11-25")
    u = plan.updates[1]
    assert f.G_CIB_PRICE not in u  # same value -> not rewritten
    assert u[f.G_LOOSE_PRICE] == 5.0
    assert u[f.G_COVER_URL] == entry("Halo 3").cover_url


def test_plan_editions_and_unknown_editions():
    rows = {1: {"id": 1}, 2: {"id": 2}}
    pairs = [(entry("Halo 3", edition="Platinum Hits"), 1), (entry("Fable", edition="Game of the Year"), 2)]
    plan = plan_updates(pairs, rows, FIELDS, ImportOptions(set_prices=False), "2026-11-25")
    assert plan.updates[1]["field_99"] == 501
    assert plan.unknown_editions == {"Game of the Year": 1}


def test_run_import_dry_run_writes_nothing():
    fake = FakeBaserow([{"id": 1, f.G_TITLE: "Halo 3", f.G_PLATFORM: X360},
                         {"id": 2, f.G_TITLE: "Fable", f.G_PLATFORM: X360}])
    s = asyncio.run(run_import(ImportOptions(dry_run=True), client=fake,
                               entries=[entry("Halo 3"), entry("250GB Hard Drive")]))
    assert fake.updated == []
    assert s.matched == 1 and s.missing == ["250GB Hard Drive"] and s.only_in_baserow == 1
    assert s.games_updated == 1 and s.prices_set == 3 and s.covers_set == 1


def test_run_import_writes():
    fake = FakeBaserow([{"id": 1, f.G_TITLE: "Halo 3", f.G_PLATFORM: X360}])
    s = asyncio.run(run_import(ImportOptions(dry_run=False), client=fake, entries=[entry("Halo 3")]))
    assert {u["id"] for u in fake.updated} == {1}
    assert s.games_updated == 1
