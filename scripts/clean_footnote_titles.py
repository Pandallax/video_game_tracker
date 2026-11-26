"""One-off cleanup: strip Wikipedia footnote-reference markers (e.g.
"[ note 10 ]", "[ broken anchor ]") that got scraped into Games titles by
scripts/import_catalog.py. Wikipedia's "List of Xbox 360 games" tables cite
some titles with a footnote link right in the title cell; the HTML-table
parser kept its text instead of dropping it. Found by comparing the
PriceCharting import's "possible_match" results against Baserow (2026-11-26) --
65 Xbox 360 rows, e.g. "Condemned: Criminal Origins [ note 10 ]" should just
be "Condemned: Criminal Origins". Only strips that specific marker shape;
leaves alone real bracketed edition labels some rows already have on purpose
(e.g. "Battlefield 1 [Early Enlister Deluxe Edition]").

Checks every platform (not just Xbox 360) since the same Wikipedia-table
parsing code is shared across all of them. If a clean title would collide
with an existing row on the same platform, that row is skipped and reported
instead of being auto-renamed/merged -- rename or merge those by hand.

Usage (run on the VM, where .env has the real Baserow token):
    cd backend && ./.venv/bin/python ../scripts/clean_footnote_titles.py [--apply]
"""
import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.baserow import field_ids as f  # noqa: E402
from app.baserow.client import baserow_client  # noqa: E402
from app.completionator import normalize  # noqa: E402

FOOTNOTE_RE = re.compile(r"\s*\[\s*(?:note\s+\d+|broken anchor)\s*\]", re.IGNORECASE)
BATCH_SIZE = 100


def clean_title(title: str) -> str | None:
    """The footnote-stripped title, or None if there was no footnote marker to
    strip (so unrelated whitespace quirks elsewhere in a title aren't touched)."""
    if not FOOTNOTE_RE.search(title):
        return None
    return " ".join(FOOTNOTE_RE.sub("", title).split())


async def main() -> int:
    apply = "--apply" in sys.argv

    rows = await baserow_client.list_rows(f.TABLE_GAMES)
    by_platform: dict[str, list[dict]] = {}
    for row in rows:
        platform = (row.get(f.G_PLATFORM) or {}).get("value")
        by_platform.setdefault(platform, []).append(row)

    renames: dict[int, str] = {}
    conflicts: list[tuple[int, str, str]] = []  # id, old title, clashing title

    for platform, platform_rows in by_platform.items():
        existing_norms = {normalize(r.get(f.G_TITLE) or "") for r in platform_rows}
        for row in platform_rows:
            title = row.get(f.G_TITLE) or ""
            cleaned = clean_title(title)
            if cleaned is None:
                continue
            norm = normalize(cleaned)
            other_titles = existing_norms - {normalize(title)}
            if norm in other_titles:
                conflicts.append((row["id"], title, cleaned))
            else:
                renames[row["id"]] = cleaned

    print(f"{len(renames)} titles to clean across {len(by_platform)} platforms")
    for row_id, cleaned in sorted(renames.items()):
        print(f"  {row_id}: -> {cleaned!r}")
    if conflicts:
        print(f"\n{len(conflicts)} skipped -- clean title collides with an existing row (fix by hand):")
        for row_id, old, cleaned in conflicts:
            print(f"  {row_id}: {old!r} -> {cleaned!r}")

    if not apply:
        print("\nDry run, nothing written. Re-run with --apply to write.")
        return 0

    items = [{"id": row_id, f.G_TITLE: cleaned} for row_id, cleaned in renames.items()]
    for i in range(0, len(items), BATCH_SIZE):
        await baserow_client.batch_update_rows(f.TABLE_GAMES, items[i : i + BATCH_SIZE])
    print(f"\nDone. Renamed {len(renames)} games.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
