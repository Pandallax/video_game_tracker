"""One-time import of Xbox 360 prices, box art and editions from
PriceCharting into the Games table.

PriceCharting's bulk CSV/API require a paid "Legendary" subscription, so this
instead walks the public, non-API console listing page
(https://www.pricecharting.com/console/xbox-360) that each game's existing
PriceCharting link already points into -- paginating via the same
cursor-based "more results" form its own page JS uses (see fetch_console()),
not a saved/cached copy. robots.txt only disallows /stripe-connect,
/publish-offer and /buy, so this is allowed; it is a different data path from
their paid API/CSV, which is licensed for internal use only -- this script is
for this collection's personal, one-time use, never for resale or republishing.

CLI only (scripts/import_pricecharting.py) -- no Dashboard panel, since this
is a one-time catalog fill rather than an ongoing sync like the Completionator
import.
"""
import re
from dataclasses import dataclass, field
from datetime import date

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

from app.baserow import field_ids as f
from app.baserow.game_fields import edition_write_value, find_edition_field
from app.completionator import Comparison, compare, normalize
from app.schemas import edition_from_value

BASE_URL = "https://www.pricecharting.com"
CONSOLE_SLUG = "xbox-360"
PLATFORM = "Xbox 360"
USER_AGENT = (
    "video-game-tracker-pricecharting-import/1.0 "
    "(personal hobby project, one-time internal use; contact pandallax@pandallax.com)"
)
BATCH_SIZE = 100

# PriceCharting shows a variant/edition in a trailing "[...]", e.g.
# "Halo 3 [Platinum Hits]" or "007 Quantum of Solace [Collector's Edition]".
EDITION_RE = re.compile(r"\s*\[([^\[\]]+)\]\s*$")

PRICE_COLUMNS = {"loose": "G_LOOSE_PRICE", "cib": "G_CIB_PRICE", "new": "G_SEALED_PRICE"}


@dataclass(frozen=True)
class Entry:
    title: str
    edition: str
    loose: float | None
    cib: float | None
    new: float | None
    url: str
    cover_url: str

    @property
    def baserow_title(self) -> str:
        return f"{self.title} ({self.edition})" if self.edition else self.title


def _cell_price(cell) -> float | None:
    span = cell.find(class_="js-price") if cell else None
    if span is None:
        return None
    match = re.search(r"[\d,]+\.?\d*", span.get_text(strip=True))
    return float(match.group().replace(",", "")) if match else None


def parse_row(row_html: str) -> Entry | None:
    """row_html: a single <tr id="product-...">...</tr> from the console listing table."""
    row = BeautifulSoup(row_html, "lxml")
    title_cell = row.find("td", class_="title")
    link = title_cell.find("a") if title_cell else None
    if link is None:
        return None
    raw_title = " ".join(link.get_text(" ", strip=True).split())
    m = EDITION_RE.search(raw_title)
    edition = m.group(1).strip() if m else ""
    title = EDITION_RE.sub("", raw_title).strip()
    if not title:
        return None
    image_cell = row.find("td", class_="image")
    img = image_cell.find("img") if image_cell else None
    return Entry(
        title=title,
        edition=edition,
        loose=_cell_price(row.find("td", class_=re.compile(r"\bused_price\b"))),
        cib=_cell_price(row.find("td", class_=re.compile(r"\bcib_price\b"))),
        new=_cell_price(row.find("td", class_=re.compile(r"\bnew_price\b"))),
        url=f"{BASE_URL}{link['href']}" if link.get("href") else "",
        cover_url=img["src"] if img and img.get("src") else "",
    )


def parse_page(html: str) -> tuple[list[Entry], str | None]:
    """Entries on one console-listing page, plus the next page's cursor (None past the last page)."""
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select("tr[id^='product-']")
    entries = [e for row in rows if (e := parse_row(str(row))) is not None]
    next_form = soup.find("form", class_="next_page")
    cursor = None
    if next_form:
        cursor_input = next_form.find("input", attrs={"name": "cursor"})
        cursor = cursor_input["value"] if cursor_input else None
    return entries, cursor


def unique(entries: list[Entry]) -> list[Entry]:
    """Drop duplicate title+edition rows (PriceCharting lists some twice, e.g. re-releases)."""
    seen: set[tuple[str, str]] = set()
    out = []
    for e in entries:
        key = (normalize(e.title), normalize(e.edition))
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


async def fetch_console(console: str = CONSOLE_SLUG) -> list[Entry]:
    """All entries for a console, walking PriceCharting's own cursor pagination."""
    entries: list[Entry] = []
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=60) as client:
        resp = await client.get(f"{BASE_URL}/console/{console}", params={"sort": "name"})
        resp.raise_for_status()
        page_entries, cursor = parse_page(resp.text)
        entries.extend(page_entries)
        while cursor is not None:
            resp = await client.post(
                f"{BASE_URL}/console/{console}",
                params={"sort": "name"},
                data={"sort": "name", "when": "none", "release-date": date.today().isoformat(), "cursor": cursor},
            )
            resp.raise_for_status()
            page_entries, cursor = parse_page(resp.text)
            entries.extend(page_entries)
    return entries


# ---- Applying an import ----


class ImportOptions(BaseModel):
    dry_run: bool = True  # report what would change, write nothing
    set_prices: bool = True
    overwrite_prices: bool = False
    set_covers: bool = True
    overwrite_covers: bool = False
    set_editions: bool = True


class PossibleMatch(BaseModel):
    checklist_title: str
    baserow_title: str
    row_id: int
    score: float


class ImportSummary(BaseModel):
    dry_run: bool
    fetched: int  # rows parsed from PriceCharting (games, bundles and hardware alike)
    checklist_entries: int  # after de-duplication
    baserow_games: int  # Xbox 360 games in Baserow before the import
    matched: int
    possible_matches: list[PossibleMatch]
    missing: list[str]  # PriceCharting titles with no Baserow match (mostly hardware/bundles, not games)
    only_in_baserow: int
    games_updated: int
    prices_set: int
    covers_set: int
    editions_set: int
    unknown_editions: dict[str, int]  # edition -> games, not an option on Editions yet
    notes: list[str]


@dataclass
class _Plan:
    updates: dict[int, dict] = field(default_factory=dict)
    prices: int = 0
    covers: int = 0
    editions: int = 0
    unknown_editions: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def set(self, row_id: int, key: str, value) -> None:
        self.updates.setdefault(row_id, {})[key] = value


def plan_updates(
    matched: list[tuple[Entry, int]],
    row_by_id: dict[int, dict],
    fields: list[dict],
    options: ImportOptions,
    today: str,
) -> _Plan:
    """Work out every field change for matched games (no I/O)."""
    plan = _Plan()

    if options.set_prices:
        targets = {col: getattr(f, attr) for col, attr in PRICE_COLUMNS.items() if getattr(f, attr)}
        for e, row_id in matched:
            row = row_by_id[row_id]
            for column, key in targets.items():
                price = getattr(e, column)
                current = row.get(key)
                has_current = current not in (None, "")
                if price is None or (has_current and not options.overwrite_prices):
                    continue
                if has_current and float(current) == price:
                    continue  # unchanged -- don't bump Price updated
                plan.set(row_id, key, price)
                plan.prices += 1
                if f.G_PRICE_UPDATED:
                    plan.set(row_id, f.G_PRICE_UPDATED, today)

    if options.set_editions:
        edition_fld = find_edition_field(fields)
        if edition_fld is None:
            plan.notes.append('No "Editions" field on Games -- editions skipped')
        else:
            for e, row_id in matched:
                if not e.edition or edition_from_value(row_by_id[row_id].get(edition_fld.key)):
                    continue
                try:
                    plan.set(row_id, edition_fld.key, edition_write_value(edition_fld, e.edition))
                    plan.editions += 1
                except ValueError:
                    plan.unknown_editions[e.edition] = plan.unknown_editions.get(e.edition, 0) + 1

    if options.set_covers:
        if f.G_COVER_URL is None:
            plan.notes.append('No "Cover URL" field on Games -- covers skipped')
        else:
            for e, row_id in matched:
                current = row_by_id[row_id].get(f.G_COVER_URL)
                if not e.cover_url or current == e.cover_url:
                    continue
                if current and not options.overwrite_covers:
                    continue
                plan.set(row_id, f.G_COVER_URL, e.cover_url)
                plan.covers += 1

    return plan


async def run_import(
    options: ImportOptions,
    client=None,
    entries: list[Entry] | None = None,
    on_compare=None,
) -> ImportSummary:
    """Fetch the PriceCharting console listing, match it against Baserow's Xbox
    360 games and (unless dry_run) write the changes."""
    if client is None:
        from app.baserow.client import baserow_client as client  # lazy: needs .env

    if entries is None:
        entries = await fetch_console()
    fetched = len(entries)
    checklist = unique(entries)

    rows = await client.list_rows(f.TABLE_GAMES)
    fields = await client.list_fields(f.TABLE_GAMES)
    platform_rows = [r for r in rows if (r.get(f.G_PLATFORM) or {}).get("value") == PLATFORM]
    row_by_id = {r["id"]: r for r in platform_rows}
    games = [(r["id"], r.get(f.G_TITLE) or "") for r in platform_rows]

    comparison: Comparison = compare(checklist, games)
    if on_compare:
        on_compare(comparison, dict(games))

    plan = plan_updates(comparison.matched, row_by_id, fields, options, date.today().isoformat())

    if not options.dry_run and plan.updates:
        items = [{"id": row_id, **values} for row_id, values in plan.updates.items()]
        for i in range(0, len(items), BATCH_SIZE):
            await client.batch_update_rows(f.TABLE_GAMES, items[i : i + BATCH_SIZE])

    return ImportSummary(
        dry_run=options.dry_run,
        fetched=fetched,
        checklist_entries=len(checklist),
        baserow_games=len(platform_rows),
        matched=len(comparison.matched),
        possible_matches=[
            PossibleMatch(checklist_title=e.baserow_title, baserow_title=title, row_id=rid, score=round(score, 2))
            for e, rid, title, score in comparison.possible
        ],
        missing=[e.baserow_title for e in comparison.missing],
        only_in_baserow=len(comparison.only_in_baserow),
        games_updated=len(plan.updates),
        prices_set=plan.prices,
        covers_set=plan.covers,
        editions_set=plan.editions,
        unknown_editions=plan.unknown_editions,
        notes=plan.notes,
    )
