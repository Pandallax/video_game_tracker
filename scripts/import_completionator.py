"""Compare saved Completionator checklist pages against the Games table, and
optionally add missing games, fill in market prices and store Completionator
links.

Completionator has no export, so save each page of the checklist from your
browser (Ctrl+S, "Webpage, HTML only" is enough) and pass all the files:

    https://www.completionator.com/Checklist/microsoft-xbox-na-physical-games

Each row has a title, an Edition (blank for the original release, or e.g.
"Platinum Hits"), and loose / complete / new prices. Editions map to this
app's convention of a separate "Title (Edition)" row whose Upgrade to points
at the base title, with Target off (see README).

By default the script only reports -- it writes completionator_report.csv in
the current directory and changes nothing. Add flags to write:

    --add-missing      create Games rows for checklist entries with no match
    --set-prices [KIND ...]
                       fill prices from the checklist: loose -> Loose Price,
                       complete -> CIB Price, new -> Sealed Price. All
                       three by default, or name the ones you want.
                       Only fills empty prices unless --overwrite-prices
    --set-links        fill "Completionator URL" (if that field exists)

Titles that look close but aren't exact (e.g. punctuation differences) are
reported as possible_match and are never auto-added, so they don't become
duplicates. Rename them in Baserow to match, then re-run.

Usage (run on the VM, where .env has the real Baserow token):
    cd backend && ./.venv/bin/python ../scripts/import_completionator.py ~/checklist/*.htm \\
        [--platform "OG Xbox"] [--add-missing] [--set-prices] [--set-links]
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

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.baserow import field_ids as f  # noqa: E402

REPORT_PATH = "completionator_report.csv"
POSSIBLE_MATCH_THRESHOLD = 0.85
BATCH_SIZE = 100


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

    @property
    def baserow_title(self) -> str:
        return f"{self.title} ({self.edition})" if self.edition else self.title


def parse_price(text: str) -> float | None:
    match = re.search(r"\d[\d,]*(?:\.\d+)?", text)
    return float(match.group().replace(",", "")) if match else None


def parse_checklist(html: str) -> list[Entry]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="cgpager-results-container")
    if table is None:
        raise ValueError("no checklist table found (is this a saved Completionator checklist page?)")

    header = [th.get("id", "") for th in table.find("tr").find_all("th")]
    col = {name: i for i, name in enumerate(header)}
    required = ["srtGameName", "srtEdition", "srtCompletePrice"]
    if any(name not in col for name in required):
        raise ValueError(f"unexpected checklist columns: {header}")

    def cell(cells, name: str) -> str:
        i = col.get(name)
        return cells[i].get_text(" ", strip=True) if i is not None and i < len(cells) else ""

    entries = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < len(header):
            continue
        link = cells[col["srtGameName"]].find("a")
        title = cell(cells, "srtGameName")
        if not title:
            continue
        entries.append(
            Entry(
                title=title,
                edition=cell(cells, "srtEdition"),
                genre=cell(cells, "srtGenre"),
                loose=parse_price(cell(cells, "srtLoosePrice")),
                complete=parse_price(cell(cells, "srtCompletePrice")),
                new=parse_price(cell(cells, "srtNewPrice")),
                release_type=cell(cells, "srtReleaseTypeName"),
                release_date=cell(cells, "srtReleaseDate"),
                url=link["href"] if link and link.get("href") else "",
            )
        )
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
        return [e.loose, e.complete, e.new, e.url]

    with open(REPORT_PATH, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["status", "checklist_title", "edition", "baserow_row_id", "baserow_title", "score",
                    "loose", "complete", "new", "completionator_url"])
        for e in comparison.missing:
            w.writerow(["missing_in_baserow", e.title, e.edition, "", "", ""] + price_cols(e))
        for e, row_id, title, score in comparison.possible:
            w.writerow(["possible_match", e.title, e.edition, row_id, title, f"{score:.2f}"] + price_cols(e))
        for row_id, title in comparison.only_in_baserow:
            w.writerow(["only_in_baserow", "", "", row_id, title, "", "", "", "", ""])
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
    parser.add_argument("files", nargs="+", type=Path, help="saved checklist pages (.htm/.html)")
    parser.add_argument("--platform", default="OG Xbox", choices=list(f.PLATFORM_OPTIONS))
    parser.add_argument("--include-unofficial", action="store_true", help="keep non-'Official Release' rows")
    parser.add_argument("--add-missing", action="store_true")
    parser.add_argument("--set-prices", nargs="*", choices=list(PRICE_COLUMNS), metavar="KIND",
                        help="loose / complete / new (default: all three)")
    parser.add_argument("--overwrite-prices", action="store_true")
    parser.add_argument("--set-links", action="store_true")
    args = parser.parse_args()

    entries: list[Entry] = []
    seen: set[tuple[str, str]] = set()
    for path in args.files:
        page = parse_checklist(path.read_text(encoding="utf-8", errors="replace"))
        print(f"{path.name}: {len(page)} rows")
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
    platform_rows = [r for r in rows if (r.get(f.G_PLATFORM) or {}).get("value") == args.platform]
    row_by_id = {r["id"]: r for r in platform_rows}
    games = [(r["id"], r.get(f.G_TITLE) or "") for r in platform_rows]
    comparison = compare(entries, games)
    write_report(comparison, dict(games))

    print(f"\n{args.platform}: {len(platform_rows)} games in Baserow")
    print(f"  matched:            {len(comparison.matched)}")
    print(f"  possible matches:   {len(comparison.possible)}  (close titles -- rename one side, re-run)")
    print(f"  missing in Baserow: {len(comparison.missing)}")
    print(f"  only in Baserow:    {len(comparison.only_in_baserow)}  (expected until every page is saved)")
    print(f"  -> {REPORT_PATH}")

    if args.add_missing and comparison.missing:
        # Base releases first so editions can link to them via Upgrade to.
        base_ids = {normalize(t): rid for rid, t in games}
        bases = [e for e in comparison.missing if not e.edition]
        for i in range(0, len(bases), BATCH_SIZE):
            created = await baserow_client.batch_create_rows(f.TABLE_GAMES, [
                {f.G_TITLE: e.title, f.G_PLATFORM: f.PLATFORM_OPTIONS[args.platform], f.G_TARGET: True}
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
                item = {f.G_TITLE: e.baserow_title, f.G_PLATFORM: f.PLATFORM_OPTIONS[args.platform], f.G_TARGET: False}
                if base_id := base_ids.get(normalize(e.title)):
                    item[f.G_UPGRADE_TO] = [base_id]
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
                if price is None or (row_by_id[row_id].get(field) and not args.overwrite_prices):
                    continue
                values = updates.setdefault(row_id, {})
                values[field] = price
                if price_updated:
                    values[price_updated] = today
    if args.set_links:
        link_field = await optional_field(baserow_client, "Completionator URL")
        if link_field is None:
            print('No "Completionator URL" field on Games -- skipping links')
        else:
            for e, row_id in comparison.matched:
                if e.url and not row_by_id[row_id].get(link_field):
                    updates.setdefault(row_id, {})[link_field] = e.url

    if updates:
        items = [{"id": row_id, **values} for row_id, values in updates.items()]
        for i in range(0, len(items), BATCH_SIZE):
            await baserow_client.batch_update_rows(f.TABLE_GAMES, items[i : i + BATCH_SIZE])
        print(f"Updated prices/links on {len(items)} games")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
