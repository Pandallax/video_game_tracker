"""Discover Baserow table schemas reachable with the configured database API token.

Database tokens only grant access to row/field data for specific tables, not the
workspace/application listing endpoints. So we start from known table IDs and
follow any "link to table" fields to auto-discover related tables.
"""
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent

# Known starting tables: name -> table_id
SEED_TABLES = {
    "Games": 1374,
    "Copies": 1375,
    "Sales": 1376,
}


def load_env(path: Path) -> dict:
    env = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def fetch_fields(base_url: str, headers: dict, table_id: int) -> list:
    resp = requests.get(
        f"{base_url}/api/database/fields/table/{table_id}/", headers=headers, timeout=10
    )
    resp.raise_for_status()
    return resp.json()


def fetch_sample_row(base_url: str, headers: dict, table_id: int) -> dict | None:
    resp = requests.get(
        f"{base_url}/api/database/rows/table/{table_id}/",
        headers=headers,
        params={"size": 1},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return results[0] if results else None


def truncate_row(row: dict, max_items: int = 3) -> dict:
    truncated = {}
    for key, value in row.items():
        if isinstance(value, list) and len(value) > max_items:
            truncated[key] = value[:max_items] + [f"... ({len(value)} total)"]
        else:
            truncated[key] = value
    return truncated


def main() -> int:
    env = load_env(ROOT / ".env")
    base_url = env.get("BASEROW_URL", "").rstrip("/")
    token = env.get("BASEROW_API_TOKEN", "")

    if not base_url or not token:
        print("Missing BASEROW_URL or BASEROW_API_TOKEN in .env", file=sys.stderr)
        return 1

    headers = {"Authorization": f"Token {token}"}

    known_names = {v: k for k, v in SEED_TABLES.items()}
    to_visit = list(SEED_TABLES.values())
    visited = set()

    while to_visit:
        table_id = to_visit.pop(0)
        if table_id in visited:
            continue
        visited.add(table_id)

        label = known_names.get(table_id, f"Unknown table {table_id}")
        print(f"\n=== Table: {label} (id={table_id}) ===")

        try:
            fields = fetch_fields(base_url, headers, table_id)
        except requests.HTTPError as e:
            print(f"  Failed to fetch fields: {e}")
            continue

        for field in fields:
            extra = ""
            if field["type"] == "link_row":
                linked_id = field.get("link_row_table_id")
                extra = f" -> links to table id={linked_id}"
                if linked_id and linked_id not in visited:
                    to_visit.append(linked_id)
            elif field["type"] in ("single_select", "multiple_select"):
                options = [o["value"] for o in field.get("select_options", [])]
                extra = f" (options: {options})"
            print(f"  Field: {field['name']} (id={field['id']}, type={field['type']}){extra}")

        try:
            sample = fetch_sample_row(base_url, headers, table_id)
            if sample:
                print(f"  Sample row: {truncate_row(sample)}")
            else:
                print("  (table is empty)")
        except requests.HTTPError as e:
            print(f"  Failed to fetch sample row: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
