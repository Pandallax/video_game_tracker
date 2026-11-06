"""Compare Completionator's live checklist against the Games table, and
optionally add missing games/editions, fill market prices, cover art, and
Completionator links.

Fetches directly from Completionator's public checklist API -- their
robots.txt explicitly allows /CollectionChecklist for automated access, and
the page's own JS hits this same endpoint to render the table. No saved
pages needed (browser "Save Page As" can't capture it anyway: the table
loads via this AJAX call *after* the initial page load, so a saved copy of
the page is always empty).

As of writing, Completionator only curates a NA physical checklist for the
original Xbox -- Xbox 360/One/Series X aren't on the site yet -- so this
only covers "OG Xbox".

Each row has a title, an Edition (blank for the original release, or e.g.
"Platinum Hits"), loose/complete/new prices, and a box art image specific to
that printing. Editions map to this app's convention of a separate
"Title (Edition)" row whose Upgrade to points at the base title, with Target
off (see README).

By default the script only reports -- it writes completionator_report.csv in
the current directory and changes nothing. Add flags to write:

    --add-missing      create Games rows for checklist entries with no match
    --set-prices [KIND ...]
                       fill prices from the checklist: loose -> Loose Price,
                       complete -> CIB Price, new -> Sealed Price. All
                       three by default, or name the ones you want.
                       Only fills empty prices unless --overwrite-prices
    --set-links        fill "Completionator URL" (if that field exists)
    --set-editions     fill the Games "Editions" field from the checklist's
                       Edition column, for games where it's blank (editions
                       that aren't an option on that field are reported)
    --set-covers       fill Cover URL from Completionator's box art; only
                       games with no cover unless --overwrite-covers

Titles that look close but aren't exact (e.g. punctuation differences) are
reported as possible_match and are never auto-added, so they don't become
duplicates. Rename them in Baserow to match, then re-run.

Usage (run on the VM, where .env has the real Baserow token):
    cd backend && ./.venv/bin/python ../scripts/import_completionator.py \\
        [--add-missing] [--set-prices] [--set-links] [--set-editions] [--set-covers]
"""
import argparse
import asyncio
import csv
import difflib
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.baserow import field_ids as f  # noqa: E402
from app.baserow.game_fields import edition_write_value, find_edition_field  # noqa: E402
from app.schemas import edition_from_value  # noqa: E402

REPORT_PATH = "completionator_report.csv"
POSSIBLE_MATCH_THRESHOLD = 0.85
BATCH_SIZE = 100

BASE_URL = "https://www.completionator.com"
SEARCH_URL = f"{BASE_URL}/CollectionChecklist/SearchPager"
CHECKLIST_ID = "27"  # Microsoft Xbox (NTSC-U/C) -- the only platform checklist Completionator has so far
USER_AGENT = "video-game-tracker-completionator-import/1.0 (personal hobby project; contact pandallax@pandallax.com)"


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


def parse_row(row_html: str) -> Entry | None:
    soup = BeautifulSoup(f"<tr>{row_html}</tr>", "lxml")
    cells = soup.find_all("td")
    if len(cells) < 12:
        return None
    title = cells[1].get_text(" ", strip=True)
    if not title:
        return None
    link = cells[1].find("a")
    img = cells[0].find("img")
    return Entry(
        title=title,
        edition=cells[2].get_text(" ", strip=True),
        genre=cells[3].get_text(" ", strip=True),
        loose=parse_price(cells[4].get_text(" ", strip=True)),
        complete=parse_price(cells[5].get_text(" ", strip=True)),
        new=parse_price(cells[6].get_text(" ", strip=True)),
        release_type=cells[7].get_text(" ", strip=True),
        release_date=cells[8].get_text(" ", strip=True),
        url=BASE_URL + link["href"] if link and link.get("href") else "",
        cover_url=img["src"] if img and img.get("src") else "",
    )


def parse_rows(row_htmls: list[str]) -> list[Entry]:
    return [e for html in row_htmls if (e := parse_row(html)) is not None]


def fetch_checklist(client: httpx.Client) -> list[Entry]:
    resp = client.post(
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
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    entries = parse_rows(data["results"])
    if len(entries) != data["totalCount"]:
        print(f"WARNING: fetched {len(entries)} rows but server reports {data['totalCount']} total", file=sys.stderr)
    return entries


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


def write_report(comparison: Comparison, titles_by_id: dict[int, str]) -> None:
    def price_cols(e: Entry):
        return [e.loose, e.complete, e.new, e.url, e.cover_url]

    with open(REPORT_PATH, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["status", "checklist_title", "edition", "baserow_row_id", "baserow_title", "score",
                    "loose", "complete", "new", "completionator_url", "cover_url"])
        for e in comparison.missing:
            w.writerow(["missing_in_baserow", e.title, e.edition, "", "", ""] + price_cols(e))
        for e, row_id, title, score in comparison.possible:
            w.writerow(["possible_match", e.title, e.edition, row_id, title, f"{score:.2f}"] + price_cols(e))
        for row_id, title in comparison.only_in_baserow:
            w.writerow(["only_in_baserow", "", "", row_id, title, "", "", "", "", "", ""])
        for e, row_id in comparison.matched:
            w.writerow(["matched", e.title, e.edition, row_id, titles_by_id[row_id], "1.00"] + price_cols(e))


async def optional_field(client, name: str) -> str | None:
    for field in await client.list_fields(f.TABLE_GAMES):
        if field["name"].strip().lower() == name.lower():
            return f"field_{field['id']}"
    return None


# Checklist column -> (field_ids attribute, Baserow field name to look up if that attribute is None)
PRICE_COLUMNS = {
    "loose": ("G_LOOSE_PRICE", "Loose Price"),
    "complete": ("G_CIB_PRICE", "CIB Price"),
    "new": ("G_SEALED_PRICE", "Sealed Price"),
}


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--include-unofficial", action="store_true", help="keep non-'Official Release' rows")
    parser.add_argument("--add-missing", action="store_true")
    parser.add_argument("--set-prices", nargs="*", choices=list(PRICE_COLUMNS), metavar="KIND",
                        help="loose / complete / new (default: all three)")
    parser.add_argument("--overwrite-prices", action="store_true")
    parser.add_argument("--set-links", action="store_true")
    parser.add_argument("--set-editions", action="store_true")
    parser.add_argument("--set-covers", action="store_true")
    parser.add_argument("--overwrite-covers", action="store_true")
    args = parser.parse_args()

    platform = "OG Xbox"

    with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
        page = fetch_checklist(client)
    print(f"Fetched {len(page)} rows from Completionator")

    seen: set[tuple[str, str]] = set()
    entries: list[Entry] = []
    for e in page:
        if not args.include_unofficial and e.release_type.lower() != "official release":
            continue
        key = (normalize(e.title), normalize(e.edition))
        if key not in seen:
            seen.add(key)
            entries.append(e)
    editions = sum(1 for e in entries if e.edition)
    print(f"{len(entries)} checklist entries ({len(entries) - editions} base releases, {editions} editions)")

    from app.baserow.client import baserow_client  # noqa: E402 -- needs .env, so imported after arg parsing

    rows = await baserow_client.list_rows(f.TABLE_GAMES)
    platform_rows = [r for r in rows if (r.get(f.G_PLATFORM) or {}).get("value") == platform]
    row_by_id = {r["id"]: r for r in platform_rows}
    games = [(r["id"], r.get(f.G_TITLE) or "") for r in platform_rows]
    comparison = compare(entries, games)
    write_report(comparison, dict(games))

    print(f"\n{platform}: {len(platform_rows)} games in Baserow")
    print(f"  matched:            {len(comparison.matched)}")
    print(f"  possible matches:   {len(comparison.possible)}  (close titles -- rename one side, re-run)")
    print(f"  missing in Baserow: {len(comparison.missing)}")
    print(f"  only in Baserow:    {len(comparison.only_in_baserow)}")
    print(f"  -> {REPORT_PATH}")

    edition_fld = find_edition_field(await baserow_client.list_fields(f.TABLE_GAMES))

    if args.add_missing and comparison.missing:
        # Base releases first so editions can link to them via Upgrade to.
        base_ids = {normalize(t): rid for rid, t in games}
        bases = [e for e in comparison.missing if not e.edition]
        for i in range(0, len(bases), BATCH_SIZE):
            created = await baserow_client.batch_create_rows(f.TABLE_GAMES, [
                {f.G_TITLE: e.title, f.G_PLATFORM: f.PLATFORM_OPTIONS[platform], f.G_TARGET: True}
                for e in bases[i : i + BATCH_SIZE]
            ])
            for e, row in zip(bases[i : i + BATCH_SIZE], created):
                base_ids[normalize(e.title)] = row["id"]
                row_by_id[row["id"]] = row
                comparison.matched.append((e, row["id"]))

        edition_entries = [e for e in comparison.missing if e.edition]
        for i in range(0, len(edition_entries), BATCH_SIZE):
            chunk = edition_entries[i : i + BATCH_SIZE]
            items = []
            for e in chunk:
                item = {f.G_TITLE: e.baserow_title, f.G_PLATFORM: f.PLATFORM_OPTIONS[platform], f.G_TARGET: False}
                if base_id := base_ids.get(normalize(e.title)):
                    item[f.G_UPGRADE_TO] = [base_id]
                if edition_fld:
                    try:
                        item[edition_fld.key] = edition_write_value(edition_fld, e.edition)
                    except ValueError:
                        pass  # not an option on the Editions field; --set-editions reports these
                items.append(item)
            created = await baserow_client.batch_create_rows(f.TABLE_GAMES, items)
            for e, row in zip(chunk, created):
                row_by_id[row["id"]] = row
                comparison.matched.append((e, row["id"]))
        print(f"\nAdded {len(bases)} base games and {len(edition_entries)} editions")

    updates: dict[int, dict] = {}
    if args.set_prices is not None:
        price_updated = await optional_field(baserow_client, "Price updated")
        today = date.today().isoformat()
        targets: dict[str, str] = {}
        for column in args.set_prices or list(PRICE_COLUMNS):
            attr, name = PRICE_COLUMNS[column]
            field = getattr(f, attr) or await optional_field(baserow_client, name)
            if field is None:
                print(f'No "{name}" field on Games -- skipping {column} prices')
            else:
                targets[column] = field
        for e, row_id in comparison.matched:
            for column, field in targets.items():
                price = getattr(e, column)
                current = row_by_id[row_id].get(field)
                if price is None or (current and not args.overwrite_prices):
                    continue
                if current not in (None, "") and float(current) == price:
                    continue  # unchanged -- don't bump Price updated
                values = updates.setdefault(row_id, {})
                values[field] = price
                if price_updated:
                    values[price_updated] = today
    if args.set_editions:
        if edition_fld is None:
            print('No "Editions" field on Games -- skipping editions')
        else:
            unknown: dict[str, int] = {}
            for e, row_id in comparison.matched:
                if not e.edition or edition_from_value(row_by_id[row_id].get(edition_fld.key)):
                    continue
                try:
                    updates.setdefault(row_id, {})[edition_fld.key] = edition_write_value(edition_fld, e.edition)
                except ValueError:
                    unknown[e.edition] = unknown.get(e.edition, 0) + 1
            for name, count in sorted(unknown.items()):
                print(f'  Edition "{name}" ({count} games) is not an option on Editions -- add it in Baserow and re-run')
    if args.set_links:
        link_field = await optional_field(baserow_client, "Completionator URL")
        if link_field is None:
            print('No "Completionator URL" field on Games -- skipping links')
        else:
            for e, row_id in comparison.matched:
                if e.url and not row_by_id[row_id].get(link_field):
                    updates.setdefault(row_id, {})[link_field] = e.url
    if args.set_covers:
        cover_field = await optional_field(baserow_client, "Cover URL")
        if cover_field is None:
            print('No "Cover URL" field on Games -- skipping covers')
        else:
            for e, row_id in comparison.matched:
                if e.cover_url and (args.overwrite_covers or not row_by_id[row_id].get(cover_field)):
                    updates.setdefault(row_id, {})[cover_field] = e.cover_url

    if updates:
        items = [{"id": row_id, **values} for row_id, values in updates.items()]
        for i in range(0, len(items), BATCH_SIZE):
            await baserow_client.batch_update_rows(f.TABLE_GAMES, items[i : i + BATCH_SIZE])
        print(f"Updated {len(items)} games")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
