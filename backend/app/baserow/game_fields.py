"""Games fields that are looked up by name at runtime instead of hard-coded in
field_ids.py, so they keep working as options are added in Baserow."""
import time
from dataclasses import dataclass, field

from app.baserow import field_ids as f

EDITION_FIELD_NAMES = ("editions", "edition")
CACHE_SECONDS = 300


@dataclass(frozen=True)
class EditionField:
    key: str  # "field_<id>"
    type: str  # single_select, multiple_select, text, ...
    # Option name -> option id, in Baserow's order (select fields only).
    options: dict[str, int] = field(default_factory=dict)

    @property
    def is_select(self) -> bool:
        return self.type in ("single_select", "multiple_select")


_cache: tuple[float, EditionField | None] | None = None


def find_edition_field(fields: list[dict]) -> EditionField | None:
    for fld in fields:
        if fld["name"].strip().lower() in EDITION_FIELD_NAMES:
            options = {o["value"]: o["id"] for o in fld.get("select_options") or []}
            return EditionField(key=f"field_{fld['id']}", type=fld["type"], options=options)
    return None


async def edition_field(refresh: bool = False) -> EditionField | None:
    """The Games "Editions" field, or None if it doesn't exist. Cached for a few
    minutes; pass refresh=True to re-read it (e.g. after an unknown option)."""
    from app.baserow.client import baserow_client  # lazy: scripts import this module before .env is loaded

    global _cache
    if not refresh and _cache and time.monotonic() - _cache[0] < CACHE_SECONDS:
        return _cache[1]
    found = find_edition_field(await baserow_client.list_fields(f.TABLE_GAMES))
    _cache = (time.monotonic(), found)
    return found


def edition_write_value(fld: EditionField, edition: str):
    """Baserow value for setting the edition ("" clears it). Raises ValueError
    for a name that isn't one of the field's options."""
    edition = edition.strip()
    if not fld.is_select:
        return edition
    if not edition:
        return [] if fld.type == "multiple_select" else None
    by_lower = {name.lower(): option_id for name, option_id in fld.options.items()}
    option_id = by_lower.get(edition.lower())
    if option_id is None:
        raise ValueError(edition)
    return [option_id] if fld.type == "multiple_select" else option_id
