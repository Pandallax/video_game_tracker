"""One-time import of Xbox 360 prices, box art and editions from PriceCharting
(see backend/app/pricecharting.py for why this scrapes the public console page
instead of PriceCharting's paid API/CSV). Compares it with the Games table and
writes pricecharting_report.csv in the current directory. It changes nothing
unless given at least one of these flags:

    --set-prices         fill Loose / CIB / Sealed Price from PriceCharting's
                          loose / cib / new prices (empty prices only, unless
                          --overwrite-prices)
    --set-editions       fill the Editions field (blank ones only); editions
                          that aren't an option on that field are reported
    --set-covers         fill Cover URL with PriceCharting's box art for that
                          exact printing (empty covers only, unless
                          --overwrite-covers)
    --all                all of the --set-* flags above

Add --dry-run to any of those to see the counts without writing. This is a
one-time catalog fill, not an ongoing sync -- there's no --add-missing and no
Dashboard panel; the Xbox 360 catalog is already populated from Wikipedia
(scripts/import_catalog.py).

Titles that look close but aren't exact (e.g. punctuation differences) are
reported as possible_match and are never auto-matched, so they don't get
skipped silently. Rename them in Baserow to match, then re-run. Most of
PriceCharting's "missing" entries are hardware/bundles/variants that were
never in the Wikipedia catalog -- that's expected, not a gap.

Usage (on the VM, where .env has the real Baserow token):
    cd backend && ./.venv/bin/python ../scripts/import_pricecharting.py --all
"""
import argparse
import asyncio
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.pricecharting import (  # noqa: E402,F401 -- parse_row/parse_page re-exported for tests
    Comparison,
    Entry,
    ImportOptions,
    compare,
    parse_page,
    parse_row,
    run_import,
)

REPORT_PATH = "pricecharting_report.csv"


def write_report(comparison: Comparison, titles_by_id: dict[int, str]) -> None:
    def cols(e: Entry):
        return [e.loose, e.cib, e.new, e.url, e.cover_url]

    with open(REPORT_PATH, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["status", "pricecharting_title", "edition", "baserow_row_id", "baserow_title", "score",
                    "loose", "cib", "new", "pricecharting_url", "cover_url"])
        for e in comparison.missing:
            w.writerow(["missing_in_baserow", e.title, e.edition, "", "", ""] + cols(e))
        for e, row_id, title, score in comparison.possible:
            w.writerow(["possible_match", e.title, e.edition, row_id, title, f"{score:.2f}"] + cols(e))
        for row_id, title in comparison.only_in_baserow:
            w.writerow(["only_in_baserow", "", "", row_id, title, "", "", "", "", "", ""])
        for e, row_id in comparison.matched:
            w.writerow(["matched", e.title, e.edition, row_id, titles_by_id[row_id], "1.00"] + cols(e))


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set-prices", action="store_true")
    parser.add_argument("--overwrite-prices", action="store_true")
    parser.add_argument("--set-editions", action="store_true")
    parser.add_argument("--set-covers", action="store_true")
    parser.add_argument("--overwrite-covers", action="store_true")
    parser.add_argument("--all", action="store_true", help="all --set-* flags")
    parser.add_argument("--dry-run", action="store_true", help="report counts, write nothing")
    args = parser.parse_args()

    writes = [args.set_prices, args.set_editions, args.set_covers, args.all]
    options = ImportOptions(
        dry_run=args.dry_run or not any(writes),
        set_prices=args.set_prices or args.all,
        overwrite_prices=args.overwrite_prices,
        set_covers=args.set_covers or args.all,
        overwrite_covers=args.overwrite_covers,
        set_editions=args.set_editions or args.all,
    )
    s = await run_import(options, on_compare=write_report)

    print(f"Fetched {s.fetched} rows from PriceCharting -> {s.checklist_entries} unique entries")
    print(f"Xbox 360: {s.baserow_games} games in Baserow")
    print(f"  matched:            {s.matched}")
    print(f"  possible matches:   {len(s.possible_matches)}  (close titles -- rename one side, re-run)")
    print(f"  not in Baserow:     {len(s.missing)}  (mostly PriceCharting hardware/bundles)")
    print(f"  only in Baserow:    {s.only_in_baserow}")
    print(f"  -> {REPORT_PATH}")
    verb = "Would change" if s.dry_run else "Changed"
    print(f"\n{verb} {s.games_updated} games: {s.prices_set} prices, {s.covers_set} covers, "
          f"{s.editions_set} editions")
    for name, count in sorted(s.unknown_editions.items()):
        print(f'  Edition "{name}" ({count} games) is not an option on Editions -- add it in Baserow and re-run')
    for note in s.notes:
        print(f"  {note}")
    if s.dry_run and not any(writes):
        print("\n(report only -- add --all or individual --set-* flags to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
