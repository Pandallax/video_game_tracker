"""Backfill the Games table's "Cover URL" field with box art from IGDB.

Each game is searched on IGDB by title, restricted to its platform, and the
best-matching result's cover is stored as an images.igdb.com URL. Games that
already have a Cover URL are skipped (so manual fixes are never overwritten)
unless --overwrite is passed.

Matches that weren't exact are written to igdb_fuzzy_matches.csv and misses to
igdb_unmatched.csv (in the current directory) so you can eyeball / hand-fix
them -- paste any image URL into the game's Cover URL in Baserow or the Games
page.

Setup:
  1. In Baserow, add a field named "Cover URL" (type URL) to the Games table.
  2. Register an app at https://dev.twitch.tv/console/apps (OAuth redirect
     http://localhost, category "Application Integration"), then put its
     client ID / secret in .env as IGDB_CLIENT_ID / IGDB_CLIENT_SECRET.
  3. Run scripts/discover_baserow.py and paste the Cover URL field id into
     backend/app/baserow/field_ids.py (G_COVER_URL) so the app can show it.
     (This script finds the field by name, so it works before that step.)

Usage (run on the VM, where .env has the real tokens):
    cd backend && ./.venv/bin/python ../scripts/fetch_igdb_covers.py \\
        [--dry-run] [--overwrite] [--platform "OG Xbox"] [--limit N]
"""
import argparse
import asyncio
import csv
import difflib
import re
import sys
import time
import unicodedata
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.baserow import field_ids as f  # noqa: E402
from app.baserow.client import baserow_client  # noqa: E402
from app.config import settings  # noqa: E402

COVER_FIELD_NAME = "Cover URL"
TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
IGDB_GAMES_URL = "https://api.igdb.com/v4/games"
COVER_URL_TEMPLATE = "https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg"

# IGDB platform ids
IGDB_PLATFORMS = {
    "OG Xbox": 11,
    "Xbox 360": 12,
    "Xbox One": 49,
    "Xbox Series X|S": 169,
}

# IGDB allows 4 requests/second.
REQUEST_INTERVAL = 0.27
MATCH_THRESHOLD = 0.85
BATCH_SIZE = 100

EDITION_SUFFIXES = re.compile(
    r"\s*[\(\[]?\b(platinum hits|greatest hits|classics|best of platinum)\b[\)\]]?\s*$", re.IGNORECASE
)
FOOTNOTES = re.compile(r"\[[^\]]*\]")


def search_title(title: str) -> str:
    """Title as typed into IGDB search: drop Wikipedia footnotes and reissue labels."""
    title = FOOTNOTES.sub("", title)
    title = EDITION_SUFFIXES.sub("", title)
    return title.strip()


def normalize(title: str) -> str:
    title = re.sub(r"[™®©'’]", "", title)
    title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    title = title.lower().replace("&", " and ")
    title = re.sub(r"[^a-z0-9]+", " ", title).strip()
    return re.sub(r"^the ", "", title)


def best_match(title: str, candidates: list[dict]) -> tuple[dict | None, float]:
    wanted = normalize(title)
    best, best_score = None, 0.0
    for cand in candidates:
        if not cand.get("cover"):
            continue
        names = [cand.get("name", "")] + [a.get("name", "") for a in cand.get("alternative_names", [])]
        score = max(difflib.SequenceMatcher(None, wanted, normalize(n)).ratio() for n in names)
        # Prefer the base game over special editions when names tie.
        if cand.get("version_parent"):
            score -= 0.01
        if score > best_score:
            best, best_score = cand, score
    return best, best_score


class Igdb:
    def __init__(self, client_id: str, client_secret: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._http = httpx.Client(timeout=30)
        self._token = ""
        self._last_request = 0.0

    def authenticate(self) -> None:
        resp = self._http.post(
            TWITCH_TOKEN_URL,
            params={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "client_credentials",
            },
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]

    def search(self, title: str, platform_id: int | None) -> list[dict]:
        escaped = title.replace("\\", "\\\\").replace('"', '\\"')
        query = (
            f'search "{escaped}"; '
            "fields name, alternative_names.name, cover.image_id, version_parent; "
            + (f"where platforms = ({platform_id}); " if platform_id else "")
            + "limit 10;"
        )
        for attempt in range(5):
            wait = REQUEST_INTERVAL - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()
            resp = self._http.post(
                IGDB_GAMES_URL,
                headers={"Client-ID": self._client_id, "Authorization": f"Bearer {self._token}"},
                content=query,
            )
            if resp.status_code == 429:
                time.sleep(2**attempt)
                continue
            if resp.status_code == 401 and attempt == 0:
                self.authenticate()
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError(f"IGDB kept rate-limiting the search for {title!r}")


def find_cover(igdb: Igdb, title: str, platform: str | None) -> tuple[str | None, str | None, float]:
    """Returns (cover_url, igdb_name, score)."""
    query = search_title(title)
    platform_id = IGDB_PLATFORMS.get(platform or "")
    match, score = best_match(query, igdb.search(query, platform_id))
    if match is None or score < MATCH_THRESHOLD:
        # Some games aren't tagged with every platform on IGDB; retry unfiltered
        # but only accept a (near-)exact name match.
        fallback, fb_score = best_match(query, igdb.search(query, None))
        if fallback is not None and fb_score >= 0.98:
            match, score = fallback, fb_score
    if match is None or score < MATCH_THRESHOLD:
        return None, match.get("name") if match else None, score
    return COVER_URL_TEMPLATE.format(image_id=match["cover"]["image_id"]), match.get("name"), score


def resolve_cover_field_id() -> str:
    resp = httpx.get(
        f"{settings.baserow_url.rstrip('/')}/api/database/fields/table/{f.TABLE_GAMES}/",
        headers={"Authorization": f"Token {settings.baserow_api_token}"},
        timeout=15,
    )
    resp.raise_for_status()
    for field in resp.json():
        if field["name"].strip().lower() == COVER_FIELD_NAME.lower():
            return f"field_{field['id']}"
    raise SystemExit(f'No "{COVER_FIELD_NAME}" field on the Games table -- add it in Baserow first (type URL).')


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="search IGDB but write nothing to Baserow")
    parser.add_argument("--overwrite", action="store_true", help="also re-fetch games that already have a cover")
    parser.add_argument("--platform", choices=list(IGDB_PLATFORMS), help="only this platform")
    parser.add_argument("--limit", type=int, help="stop after N games (handy for a test run)")
    args = parser.parse_args()

    cover_field = resolve_cover_field_id()
    if f.G_COVER_URL and f.G_COVER_URL != cover_field:
        print(f"Warning: field_ids.G_COVER_URL is {f.G_COVER_URL} but Baserow says {cover_field}", file=sys.stderr)

    if not settings.igdb_client_id or not settings.igdb_client_secret:
        print("Set IGDB_CLIENT_ID and IGDB_CLIENT_SECRET in .env", file=sys.stderr)
        return 1

    rows = await baserow_client.list_rows(f.TABLE_GAMES)
    todo = []
    for row in rows:
        platform = (row.get(f.G_PLATFORM) or {}).get("value")
        if args.platform and platform != args.platform:
            continue
        if row.get(cover_field) and not args.overwrite:
            continue
        todo.append((row["id"], row.get(f.G_TITLE) or "", platform))
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(rows)} games in Baserow, {len(todo)} to look up on IGDB")

    igdb = Igdb(settings.igdb_client_id, settings.igdb_client_secret)
    igdb.authenticate()

    pending: list[dict] = []
    fuzzy: list[tuple] = []
    unmatched: list[tuple] = []
    found = 0

    async def flush() -> None:
        if pending and not args.dry_run:
            await baserow_client.batch_update_rows(f.TABLE_GAMES, pending)
        pending.clear()

    for i, (row_id, title, platform) in enumerate(todo, 1):
        cover_url, igdb_name, score = find_cover(igdb, title, platform)
        if cover_url:
            found += 1
            pending.append({"id": row_id, cover_field: cover_url})
            if score < 0.999:
                fuzzy.append((row_id, platform, title, igdb_name, f"{score:.2f}", cover_url))
        else:
            unmatched.append((row_id, platform, title, igdb_name or "", f"{score:.2f}"))

        if len(pending) >= BATCH_SIZE:
            await flush()
        if i % 50 == 0 or i == len(todo):
            print(f"  {i}/{len(todo)} looked up, {found} covers found", flush=True)
    await flush()

    with open("igdb_fuzzy_matches.csv", "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["row_id", "platform", "title", "igdb_name", "score", "cover_url"])
        writer.writerows(fuzzy)
    with open("igdb_unmatched.csv", "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["row_id", "platform", "title", "closest_igdb_name", "score"])
        writer.writerows(unmatched)

    verb = "would be set (dry run)" if args.dry_run else "set"
    print(f"\nDone. {found} covers {verb}; {len(fuzzy)} fuzzy matches -> igdb_fuzzy_matches.csv; "
          f"{len(unmatched)} unmatched -> igdb_unmatched.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
