"""Bulk-import the US/NTSC game catalog from Wikipedia into the Games table.

Source: Wikipedia's "List of Xbox / Xbox 360 / Xbox One / Xbox Series X and
Series S games" pages. We parse the rendered HTML table (not wikitext) so
column-order differences between pages don't matter -- the "NA" release-date
sub-column is located dynamically from each table's two header rows.

Platinum Hits / Greatest Hits reissues aren't listed separately by Wikipedia,
so they aren't created here. Add those manually as a second "Title (Platinum
Hits)" row with Upgrade to -> the base title, only for the specific printings
that matter to you (see README).

Usage (run on the VM, where .env already has the real Baserow token):
    cd backend && ./.venv/bin/python ../scripts/import_catalog.py [--dry-run]
"""
import asyncio
import sys
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.baserow import field_ids as f  # noqa: E402
from app.baserow.client import baserow_client  # noqa: E402

WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "video-game-tracker-catalog-import/1.0 (personal hobby project; contact pandallax@pandallax.com)"

SOURCES = {
    "OG Xbox": [("List_of_Xbox_games", 1)],
    "Xbox 360": [
        ("List_of_Xbox_360_games_(A–L)", 0),
        ("List_of_Xbox_360_games_(M–Z)", 0),
    ],
    "Xbox One": [
        ("List_of_Xbox_One_games_(A–L)", 1),
        ("List_of_Xbox_One_games_(M–Z)", 1),
    ],
    "Xbox Series X|S": [("List_of_Xbox_Series_X_and_Series_S_games", 0)],
}

# OG Xbox / 360 are the completion-target platforms; One / Series X|S are
# just a running purchase log, not a target set.
DEFAULT_TARGET = {
    "OG Xbox": True,
    "Xbox 360": True,
    "Xbox One": False,
    "Xbox Series X|S": False,
}

UNRELEASED_MARKERS = {"", "unreleased", "tba", "n/a", "cancelled"}

BATCH_SIZE = 100


def fetch_table_rows(client: httpx.Client, page: str, section: int) -> list[dict]:
    resp = client.get(
        WIKI_API,
        params={"action": "parse", "page": page, "format": "json", "prop": "text", "section": section},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"{page}#{section}: {data['error']}")
    html = data["parse"]["text"]["*"]
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id="softwarelist")
    if table is None:
        raise RuntimeError(f"{page}#{section}: no table#softwarelist found")

    rows = table.find_all("tr")
    top_header = [th.get_text(strip=True) for th in rows[0].find_all("th")]
    sub_header = [th.get_text(strip=True) for th in rows[1].find_all("th")]

    leading = next((i for i, h in enumerate(top_header) if h.startswith("Release date")), None)
    na_offset = next((i for i, h in enumerate(sub_header) if h == "NA"), None)
    if leading is None or na_offset is None:
        raise RuntimeError(f"{page}#{section}: couldn't locate NA column (headers={top_header}/{sub_header})")
    na_index = leading + na_offset

    out = []
    for row in rows[2:]:
        cells = row.find_all(["th", "td"])
        if len(cells) <= na_index:
            continue
        title = cells[0].get_text(" ", strip=True)
        na_value = cells[na_index].get_text(" ", strip=True)
        if not title or title.lower() in UNRELEASED_MARKERS:
            continue
        released_na = na_value.strip().lower() not in UNRELEASED_MARKERS
        out.append({"title": title, "released_na": released_na})
    return out


def collect_platform_titles(client: httpx.Client, platform: str) -> list[str]:
    seen: set[str] = set()
    titles: list[str] = []
    for page, section in SOURCES[platform]:
        for row in fetch_table_rows(client, page, section):
            if not row["released_na"]:
                continue
            key = row["title"].lower()
            if key in seen:
                continue
            seen.add(key)
            titles.append(row["title"])
        time.sleep(0.3)
    return sorted(titles, key=str.lower)


async def existing_title_platform_pairs() -> set[tuple[str, str | None]]:
    rows = await baserow_client.list_rows(f.TABLE_GAMES)
    pairs = set()
    for row in rows:
        title = (row.get(f.G_TITLE) or "").lower()
        platform = row.get(f.G_PLATFORM)
        pairs.add((title, platform["value"] if platform else None))
    return pairs


async def main() -> int:
    dry_run = "--dry-run" in sys.argv

    existing = await existing_title_platform_pairs()
    print(f"{len(existing)} existing (title, platform) rows already in Baserow")

    total_created = 0
    with httpx.Client(headers={"User-Agent": USER_AGENT}) as wiki_client:
        for platform in SOURCES:
            print(f"\nFetching {platform} from Wikipedia...", flush=True)
            titles = collect_platform_titles(wiki_client, platform)
            print(f"  {len(titles)} NA-released titles found")

            to_create = [t for t in titles if (t.lower(), platform) not in existing]
            print(f"  {len(to_create)} new (not already in Baserow)")

            if dry_run or not to_create:
                continue

            target = DEFAULT_TARGET[platform]
            platform_option_id = f.PLATFORM_OPTIONS[platform]

            for i in range(0, len(to_create), BATCH_SIZE):
                chunk = to_create[i : i + BATCH_SIZE]
                items = [
                    {f.G_TITLE: title, f.G_PLATFORM: platform_option_id, f.G_TARGET: target} for title in chunk
                ]
                await baserow_client.batch_create_rows(f.TABLE_GAMES, items)
                total_created += len(chunk)
                print(f"  created {min(i + BATCH_SIZE, len(to_create))}/{len(to_create)}", flush=True)

    print(f"\n{'Dry run complete, nothing written.' if dry_run else f'Done. Created {total_created} new game rows.'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
