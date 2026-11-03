"""One-off cleanup: remove Xbox 360 titles from the Games table that are
Xbox Live Arcade (XBLA) or Xbox Live Indie Games (XBLIG) releases -- i.e.
digital-only, no physical disc/box ever existed. These were pulled in by
scripts/import_catalog.py because Wikipedia's "List of Xbox 360 games" tables
don't distinguish disc releases from digital-only ones in the main columns;
the distinction lives in a separate "Addons" column this script checks.

Usage (run on the VM, where .env has the real Baserow token):
    cd backend && ./.venv/bin/python ../scripts/remove_digital_only_xbla.py [--dry-run]
"""
import asyncio
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.baserow import field_ids as f  # noqa: E402
from app.baserow.client import baserow_client  # noqa: E402

WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "video-game-tracker-catalog-import/1.0 (personal hobby project; contact pandallax@pandallax.com)"

PAGES = [
    ("List_of_Xbox_360_games_(A–L)", 0),
    ("List_of_Xbox_360_games_(M–Z)", 0),
]

UNRELEASED_MARKERS = {"", "unreleased", "tba", "n/a", "cancelled"}


def fetch_digital_only_titles(client: httpx.Client) -> set[str]:
    titles: set[str] = set()
    for page, section in PAGES:
        resp = client.get(
            WIKI_API,
            params={"action": "parse", "page": page, "format": "json", "prop": "text", "section": section},
            timeout=30,
        )
        resp.raise_for_status()
        html = resp.json()["parse"]["text"]["*"]
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table", id="softwarelist")
        rows = table.find_all("tr")
        top = [th.get_text(strip=True) for th in rows[0].find_all("th")]
        sub = [th.get_text(strip=True) for th in rows[1].find_all("th")]
        leading = next(i for i, h in enumerate(top) if h.startswith("Release date"))
        na_idx = leading + next(i for i, h in enumerate(sub) if h == "NA")

        def data_index(top_idx: int) -> int:
            return top_idx if top_idx < leading else top_idx - 1 + len(sub)

        addons_idx = data_index(top.index("Addons")) if "Addons" in top else None
        if addons_idx is None:
            continue

        for row in rows[2:]:
            cells = row.find_all(["th", "td"])
            if len(cells) <= max(na_idx, addons_idx):
                continue
            title = cells[0].get_text(" ", strip=True)
            na_val = cells[na_idx].get_text(" ", strip=True)
            addons = cells[addons_idx].get_text(" ", strip=True)
            if not title or na_val.strip().lower() in UNRELEASED_MARKERS:
                continue
            if "XBLA" in addons or "XBLIG" in addons:
                titles.add(title.lower())
    return titles


async def main() -> int:
    dry_run = "--dry-run" in sys.argv

    with httpx.Client(headers={"User-Agent": USER_AGENT}) as wiki_client:
        digital_titles = fetch_digital_only_titles(wiki_client)
    print(f"{len(digital_titles)} digital-only (XBLA/XBLIG) titles found on Wikipedia")

    rows = await baserow_client.list_rows(f.TABLE_GAMES)
    to_delete = []
    for row in rows:
        platform = row.get(f.G_PLATFORM)
        if not platform or platform["value"] != "Xbox 360":
            continue
        title = (row.get(f.G_TITLE) or "").lower()
        if title in digital_titles:
            to_delete.append(row["id"])

    print(f"{len(to_delete)} matching rows in Baserow's Xbox 360 catalog")

    if dry_run:
        print("Dry run, nothing deleted.")
        return 0

    for i in range(0, len(to_delete), 200):
        chunk = to_delete[i : i + 200]
        await baserow_client.batch_delete_rows(f.TABLE_GAMES, chunk)
        print(f"  deleted {min(i + 200, len(to_delete))}/{len(to_delete)}", flush=True)

    print(f"Done. Deleted {len(to_delete)} digital-only Xbox 360 rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
