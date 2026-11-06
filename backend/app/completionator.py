"""Import prices, editions, links and box art from Completionator's OG Xbox
(NTSC-U/C) physical checklist into the Games table.

Fetches the checklist from Completionator's public checklist endpoint
(/CollectionChecklist/SearchPager -- allowed for automated access by their
robots.txt, and the same call their checklist page makes), identifying itself
with its own User-Agent. Used by the Dashboard's import panel
(app/routes/imports.py) and by scripts/import_completionator.py.
"""
import difflib
from collections.abc import Callable
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

from app.baserow import field_ids as f
from app.baserow.game_fields import edition_write_value, find_edition_field
from app.schemas import edition_from_value

BASE_URL = "https://www.completionator.com"
SEARCH_URL = f"{BASE_URL}/CollectionChecklist/SearchPager"
CHECKLIST_ID = "27"  # Microsoft Xbox (NTSC-U/C) -- the only platform checklist Completionator has so far
PLATFORM = "OG Xbox"
USER_AGENT = "video-game-tracker-completionator-import/1.0 (personal hobby project; contact pandallax@pandallax.com)"
POSSIBLE_MATCH_THRESHOLD = 0.85
BATCH_SIZE = 100

# Badge Completionator shows after some titles; never part of the name.
GOAL_SUFFIX_RE = re.compile(r"\s*goals available\s*$", re.IGNORECASE)

# Checklist column -> field_ids attribute
PRICE_COLUMNS = {"loose": "G_LOOSE_PRICE", "complete": "G_CIB_PRICE", "new": "G_SEALED_PRICE"}


@dataclass(frozen=True)
class Entry:
    title: str
    edition: str
    genre: str
    loose: float | None
    complete: float | None
    new: float | None
    release_type: str
    release_date: str
    url: str
    cover_url: str

    @property
    def baserow_title(self) -> str:
        return f"{self.title} ({self.edition})" if self.edition else self.title


def parse_price(text: str) -> float | None:
    match = re.search(r"\d[\d,]*(?:\.\d+)?", text)
    return float(match.group().replace(",", "")) if match else None


def _absolute(url: str) -> str:
    return urljoin(BASE_URL + "/", url) if url else ""


def parse_row(row_html: str) -> Entry | None:
    soup = BeautifulSoup(f"<tr>{row_html}</tr>", "lxml")
    cells = soup.find_all("td")
    if len(cells) < 12:
        return None
    # The title cell also holds a "goals available" badge for some games; the
    # game's name is the text of its first link.
    link = cells[1].find("a")
    title = " ".join((link or cells[1]).get_text(" ", strip=True).split())
    title = GOAL_SUFFIX_RE.sub("", title)
    if not title:
        return None
    img = cells[0].find("img")
    return Entry(
        title=title,
        edition=" ".join(cells[2].get_text(" ", strip=True).split()),  # "Platinum  Hits" -> "Platinum Hits"
        genre=cells[3].get_text(" ", strip=True),
        loose=parse_price(cells[4].get_text(" ", strip=True)),
        complete=parse_price(cells[5].get_text(" ", strip=True)),
        new=parse_price(cells[6].get_text(" ", strip=True)),
        release_type=cells[7].get_text(" ", strip=True),
        release_date=cells[8].get_text(" ", strip=True),
        url=_absolute(link["href"]) if link and link.get("href") else "",
        cover_url=_absolute(img["src"]) if img and img.get("src") else "",
    )


def parse_rows(row_htmls: list[str]) -> list[Entry]:
    return [e for html in row_htmls if (e := parse_row(html)) is not None]


async def fetch_checklist() -> tuple[list[Entry], int]:
    """All checklist rows, plus the total the server reports."""
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=60) as client:
        resp = await client.post(
            SEARCH_URL,
            json={
                "pageSize": 2000,
                "currentPage": 1,
                "checklistID": CHECKLIST_ID,
                "keyword": "",
                "releaseTypeID": None,
                "isInCollection": None,
                "isOnWishList": None,
                "hasEdition": None,
                "exclusiveTypeID": "0",
                "isOnPlaylist": None,
                "hasCompletion": None,
                "genreIDs": None,
                "sortColumn": "ChecklistSortName",
                "sortDirection": "ASC",
            },
        )
    resp.raise_for_status()
    data = resp.json()
    return parse_rows(data["results"]), int(data.get("totalCount", 0))


def official_unique(entries: list[Entry], include_unofficial: bool = False) -> list[Entry]:
    """Drop unofficial releases (unless asked) and duplicate title+edition rows."""
    seen: set[tuple[str, str]] = set()
    out = []
    for e in entries:
        if not include_unofficial and e.release_type.lower() != "official release":
            continue
        key = (normalize(e.title), normalize(e.edition))
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def normalize(title: str) -> str:
    title = re.sub(r"[™®©'’]", "", title)
    title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    title = title.lower().replace("&", " and ")
    title = re.sub(r"[^a-z0-9]+", " ", title).strip()
    return re.sub(r"^the ", "", title)


@dataclass
class Comparison:
    matched: list[tuple[Entry, int]]
    possible: list[tuple[Entry, int, str, float]]
    missing: list[Entry]
    only_in_baserow: list[tuple[int, str]]


def compare(entries: list[Entry], games: list[tuple[int, str]]) -> Comparison:
    """games: (row_id, title) for the platform being compared."""
    by_norm: dict[str, tuple[int, str]] = {}
    for row_id, title in games:
        by_norm.setdefault(normalize(title), (row_id, title))

    matched, unmatched = [], []
    used: set[int] = set()
    for entry in entries:
        hit = by_norm.get(normalize(entry.baserow_title))
        if hit and hit[0] not in used:
            matched.append((entry, hit[0]))
            used.add(hit[0])
        else:
            unmatched.append(entry)

    leftovers = {row_id: title for row_id, title in games if row_id not in used}
    possible, missing = [], []
    for entry in unmatched:
        wanted = normalize(entry.baserow_title)
        best_id, best_title, best_score = None, "", 0.0
        for row_id, title in leftovers.items():
            score = difflib.SequenceMatcher(None, wanted, normalize(title)).ratio()
            if score > best_score:
                best_id, best_title, best_score = row_id, title, score
        if best_id is not None and best_score >= POSSIBLE_MATCH_THRESHOLD:
            possible.append((entry, best_id, best_title, best_score))
            leftovers.pop(best_id)
        else:
            missing.append(entry)

    return Comparison(matched, possible, missing, sorted(leftovers.items(), key=lambda kv: kv[1].lower()))


# ---- Applying an import ----


class ImportOptions(BaseModel):
    dry_run: bool = True  # report what would change, write nothing
    set_prices: bool = True
    overwrite_prices: bool = False
    set_covers: bool = True
    overwrite_covers: bool = False
    set_editions: bool = True
    set_links: bool = False  # links aren't shown in the app any more
    add_missing: bool = False
    include_unofficial: bool = False


class PossibleMatch(BaseModel):
    checklist_title: str
    baserow_title: str
    row_id: int
    score: float


class ImportSummary(BaseModel):
    dry_run: bool
    fetched: int  # rows returned by Completionator
    server_total: int  # rows Completionator says the checklist has
    checklist_entries: int  # after dropping unofficial/duplicate rows
    baserow_games: int  # OG Xbox games in Baserow before the import
    matched: int
    possible_matches: list[PossibleMatch]
    missing: list[str]  # checklist titles with no Baserow game
    only_in_baserow: int
    added_games: int  # (or would add, in a dry run)
    games_updated: int  # games with at least one change
    prices_set: int  # individual price values written
    covers_set: int
    editions_set: int
    links_set: int
    unknown_editions: dict[str, int]  # edition -> games, not an option on Editions yet
    titles_fixed: int = 0  # "... goals available" titles renamed
    duplicates_removed: int = 0  # "... goals available" rows that duplicated an existing game
    duplicates_kept: list[str] = []  # such duplicates left alone because copies link to them
    notes: list[str]


@dataclass
class _Plan:
    updates: dict[int, dict] = field(default_factory=dict)
    prices: int = 0
    covers: int = 0
    editions: int = 0
    links: int = 0
    unknown_editions: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def set(self, row_id: int, key: str, value) -> None:
        self.updates.setdefault(row_id, {})[key] = value


def _field_key(fields: list[dict], name: str) -> str | None:
    for fld in fields:
        if fld["name"].strip().lower() == name.lower():
            return f"field_{fld['id']}"
    return None


def plan_updates(
    matched: list[tuple[Entry, int]],
    row_by_id: dict[int, dict],
    fields: list[dict],
    options: ImportOptions,
    today: str,
) -> _Plan:
    """Work out every field change for matched games (no I/O)."""
    plan = _Plan()
    price_updated = f.G_PRICE_UPDATED or _field_key(fields, "Price updated")

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
                if price_updated:
                    plan.set(row_id, price_updated, today)

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

    if options.set_links:
        link_key = f.G_COMPLETIONATOR_URL or _field_key(fields, "Completionator URL")
        if link_key is None:
            plan.notes.append('No "Completionator URL" field on Games -- links skipped')
        else:
            for e, row_id in matched:
                if e.url and not row_by_id[row_id].get(link_key):
                    plan.set(row_id, link_key, e.url)
                    plan.links += 1

    if options.set_covers:
        cover_key = f.G_COVER_URL or _field_key(fields, "Cover URL")
        if cover_key is None:
            plan.notes.append('No "Cover URL" field on Games -- covers skipped')
        else:
            for e, row_id in matched:
                current = row_by_id[row_id].get(cover_key)
                if not e.cover_url or current == e.cover_url:
                    continue
                if current and not options.overwrite_covers:
                    continue
                plan.set(row_id, cover_key, e.cover_url)
                plan.covers += 1

    return plan


@dataclass
class _TitleFixes:
    renames: dict[int, str] = field(default_factory=dict)  # row_id -> clean title
    deletes: list[int] = field(default_factory=list)  # duplicates of an existing game, no copies
    kept: list[str] = field(default_factory=list)  # duplicates left alone because copies link to them


def plan_title_fixes(platform_rows: list[dict]) -> _TitleFixes:
    """Rows an earlier import created with "goals available" stuck on the
    title: rename them, or remove them when they duplicate a game that's
    already there (unless copies point at them)."""
    fixes = _TitleFixes()
    clean_titles = {
        normalize(r.get(f.G_TITLE) or "") for r in platform_rows if not GOAL_SUFFIX_RE.search(r.get(f.G_TITLE) or "")
    }
    for r in platform_rows:
        title = r.get(f.G_TITLE) or ""
        if not GOAL_SUFFIX_RE.search(title):
            continue
        clean = GOAL_SUFFIX_RE.sub("", title).strip()
        if normalize(clean) not in clean_titles:
            fixes.renames[r["id"]] = clean
            clean_titles.add(normalize(clean))
        elif r.get(f.G_COPIES):
            fixes.kept.append(title)
        else:
            fixes.deletes.append(r["id"])
    return fixes


async def _add_missing(client, missing: list[Entry], games: list[tuple[int, str]], fields: list[dict]):
    """Create Games rows for missing entries; returns [(entry, new_row)]."""
    edition_fld = find_edition_field(fields)
    base_ids = {normalize(t): rid for rid, t in games}
    created_pairs: list[tuple[Entry, dict]] = []

    # Base releases first so editions can link to them via Upgrade to.
    bases = [e for e in missing if not e.edition]
    for i in range(0, len(bases), BATCH_SIZE):
        chunk = bases[i : i + BATCH_SIZE]
        rows = await client.batch_create_rows(
            f.TABLE_GAMES,
            [{f.G_TITLE: e.title, f.G_PLATFORM: f.PLATFORM_OPTIONS[PLATFORM], f.G_TARGET: True} for e in chunk],
        )
        for e, row in zip(chunk, rows):
            base_ids[normalize(e.title)] = row["id"]
            created_pairs.append((e, row))

    editions = [e for e in missing if e.edition]
    for i in range(0, len(editions), BATCH_SIZE):
        chunk = editions[i : i + BATCH_SIZE]
        items = []
        for e in chunk:
            item = {f.G_TITLE: e.baserow_title, f.G_PLATFORM: f.PLATFORM_OPTIONS[PLATFORM], f.G_TARGET: False}
            if base_id := base_ids.get(normalize(e.title)):
                item[f.G_UPGRADE_TO] = [base_id]
            items.append(item)
        rows = await client.batch_create_rows(f.TABLE_GAMES, items)
        created_pairs.extend(zip(chunk, rows))
    return created_pairs


async def run_import(
    options: ImportOptions,
    client=None,
    entries: list[Entry] | None = None,
    on_compare: Callable[[Comparison, dict[int, str]], None] | None = None,
) -> ImportSummary:
    """Fetch the checklist, match it against Baserow and (unless dry_run) write the changes."""
    if client is None:
        from app.baserow.client import baserow_client as client  # lazy: needs .env

    server_total = 0
    if entries is None:
        entries, server_total = await fetch_checklist()
    fetched = len(entries)
    checklist = official_unique(entries, options.include_unofficial)

    rows = await client.list_rows(f.TABLE_GAMES)
    fields = await client.list_fields(f.TABLE_GAMES)
    platform_rows = [r for r in rows if (r.get(f.G_PLATFORM) or {}).get("value") == PLATFORM]

    # Clean up "... goals available" rows from earlier imports first, so matching sees the fixed titles.
    fixes = plan_title_fixes(platform_rows)
    if not options.dry_run:
        if fixes.renames:
            items = [{"id": rid, f.G_TITLE: title} for rid, title in fixes.renames.items()]
            for i in range(0, len(items), BATCH_SIZE):
                await client.batch_update_rows(f.TABLE_GAMES, items[i : i + BATCH_SIZE])
        for i in range(0, len(fixes.deletes), BATCH_SIZE):
            await client.batch_delete_rows(f.TABLE_GAMES, fixes.deletes[i : i + BATCH_SIZE])
    deleted = set(fixes.deletes)
    platform_rows = [
        {**r, f.G_TITLE: fixes.renames.get(r["id"], r.get(f.G_TITLE))} for r in platform_rows if r["id"] not in deleted
    ]
    row_by_id = {r["id"]: r for r in platform_rows}
    games = [(r["id"], r.get(f.G_TITLE) or "") for r in platform_rows]
    comparison = compare(checklist, games)
    if on_compare:
        on_compare(comparison, dict(games))
    matched = list(comparison.matched)

    added = 0
    if options.add_missing and comparison.missing:
        added = len(comparison.missing)
        if not options.dry_run:
            for e, row in await _add_missing(client, comparison.missing, games, fields):
                row_by_id[row["id"]] = row
                matched.append((e, row["id"]))

    plan = plan_updates(matched, row_by_id, fields, options, date.today().isoformat())
    if options.add_missing and options.dry_run and added:
        plan.notes.append(f"{added} new games would be added; their prices/covers are filled on the real run")

    if not options.dry_run and plan.updates:
        items = [{"id": row_id, **values} for row_id, values in plan.updates.items()]
        for i in range(0, len(items), BATCH_SIZE):
            await client.batch_update_rows(f.TABLE_GAMES, items[i : i + BATCH_SIZE])

    return ImportSummary(
        dry_run=options.dry_run,
        fetched=fetched,
        server_total=server_total or fetched,
        checklist_entries=len(checklist),
        baserow_games=len(platform_rows),
        matched=len(comparison.matched),
        possible_matches=[
            PossibleMatch(checklist_title=e.baserow_title, baserow_title=title, row_id=rid, score=round(score, 2))
            for e, rid, title, score in comparison.possible
        ],
        missing=[e.baserow_title for e in comparison.missing],
        only_in_baserow=len(comparison.only_in_baserow),
        added_games=added,
        games_updated=len(plan.updates),
        prices_set=plan.prices,
        covers_set=plan.covers,
        editions_set=plan.editions,
        links_set=plan.links,
        unknown_editions=plan.unknown_editions,
        titles_fixed=len(fixes.renames),
        duplicates_removed=len(fixes.deletes),
        duplicates_kept=fixes.kept,
        notes=plan.notes,
    )
