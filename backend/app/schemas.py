from pydantic import BaseModel, Field

from app.baserow import field_ids as f

CIB_COMPONENTS = ("Disc", "Case", "Manual")

# Price kinds, in display order. Keys match GamePrices' attributes.
PRICE_KINDS = ("loose", "cib", "sealed", "box_only", "manual_only")


def price_fields() -> dict[str, str | None]:
    """Baserow field id for each price kind (None if that field isn't created yet).
    Looked up at call time so field_ids can be patched in tests."""
    return {
        "loose": f.G_LOOSE_PRICE,
        "cib": f.G_CIB_PRICE,
        "sealed": f.G_SEALED_PRICE,
        "box_only": f.G_BOX_ONLY_PRICE,
        "manual_only": f.G_MANUAL_ONLY_PRICE,
    }


def _as_price(value) -> float | None:
    return float(value) if value not in (None, "") else None


def changed_price_fields(old: dict | None, new: dict) -> list[str]:
    """Price field ids whose value differs between two Games rows (or row
    fragments). Baserow returns numbers as strings like "12.00", so compare
    numerically. Fields missing from `new` are treated as unchanged; with no
    `old` row (a new game), any price that is set counts as a change."""
    changed = []
    for field in price_fields().values():
        if not field or field not in new:
            continue
        before = _as_price((old or {}).get(field))
        if _as_price(new[field]) != before:
            changed.append(field)
    return changed


class GamePrices(BaseModel):
    """Market prices by condition. On update, only the kinds that are sent are
    changed; send null to clear one."""

    loose: float | None = None  # disc only
    cib: float | None = None  # complete in box
    sealed: float | None = None  # new / factory sealed
    box_only: float | None = None
    manual_only: float | None = None


class GameOut(BaseModel):
    id: int
    title: str
    platform: str | None
    target: bool
    upgrade_to_id: int | None
    prices: GamePrices
    # Which price kinds have a Baserow field; writes to the others are rejected.
    price_kinds: list[str]
    price_updated: str | None
    cib_requires: list[str]
    upc: str
    cover_url: str | None
    completionator_url: str | None
    notes: str


class GameCreate(BaseModel):
    title: str
    platform: str
    target: bool = True
    upgrade_to_id: int | None = None
    prices: GamePrices | None = None
    cib_requires: list[str] = list(CIB_COMPONENTS)
    upc: str = ""
    cover_url: str | None = None
    notes: str = ""


class GameUpdate(BaseModel):
    title: str | None = None
    platform: str | None = None
    target: bool | None = None
    upgrade_to_id: int | None = None
    prices: GamePrices | None = None
    cib_requires: list[str] | None = None
    upc: str | None = None
    # Empty string clears the cover.
    cover_url: str | None = None
    notes: str | None = None


class CopyOut(BaseModel):
    id: int
    copy_id: str
    game_id: int | None
    game_title: str | None
    status: str | None
    sealed: bool
    has_disc: bool
    disc_quality: int | None
    has_case: bool
    case_quality: int | None
    has_manual: bool
    manual_quality: int | None
    overall_quality: float | None
    completeness: str
    purchase_price: float | None
    purchase_date: str | None
    purchased_from: str
    location: str
    notes: str
    photo_url: str | None


class CopyCreate(BaseModel):
    copy_id: str
    game_id: int
    status: str = "Collection"
    sealed: bool = False
    has_disc: bool = False
    disc_quality: int | None = Field(default=None, ge=1, le=10)
    has_case: bool = False
    case_quality: int | None = Field(default=None, ge=1, le=10)
    has_manual: bool = False
    manual_quality: int | None = Field(default=None, ge=1, le=10)
    purchase_price: float | None = None
    purchase_date: str | None = None
    purchased_from: str = ""
    location: str = ""
    notes: str = ""


class CopyUpdate(BaseModel):
    status: str | None = None
    sealed: bool | None = None
    has_disc: bool | None = None
    disc_quality: int | None = Field(default=None, ge=1, le=10)
    has_case: bool | None = None
    case_quality: int | None = Field(default=None, ge=1, le=10)
    has_manual: bool | None = None
    manual_quality: int | None = Field(default=None, ge=1, le=10)
    purchase_price: float | None = None
    purchase_date: str | None = None
    purchased_from: str | None = None
    location: str | None = None
    notes: str | None = None


class SaleOut(BaseModel):
    id: int
    sale_id: str
    copy_id: int | None
    copy_label: str | None
    sold_on: str | None
    sale_date: str | None
    sale_price: float | None
    fees: float | None
    shipping_cost: float | None
    net: float | None


class SaleCreate(BaseModel):
    sale_id: str
    copy_id: int
    sold_on: str
    sale_date: str | None = None
    sale_price: float | None = None
    fees: float | None = None
    shipping_cost: float | None = None


class PlatformStats(BaseModel):
    platform: str
    owned: int
    total: int


def normalize_upc(upc: str) -> str:
    """Strip non-digits and leading zeros so UPC-A and its EAN-13 zero-prefixed
    form compare equal (e.g. a scanner reading "0012345678905" vs a label
    printed "12345678905")."""
    digits = "".join(c for c in upc if c.isdigit())
    return digits.lstrip("0") or digits


def _number(row: dict, field: str | None) -> float | None:
    return _as_price(row.get(field)) if field else None


def game_row_to_out(row: dict) -> GameOut:
    platform = row.get(f.G_PLATFORM)
    upgrade = row.get(f.G_UPGRADE_TO) or []
    cib_requires = [opt["value"] for opt in (row.get(f.G_CIB_REQUIRES) or [])]
    return GameOut(
        id=row["id"],
        title=row.get(f.G_TITLE) or "",
        platform=platform["value"] if platform else None,
        target=bool(row.get(f.G_TARGET)),
        upgrade_to_id=upgrade[0]["id"] if upgrade else None,
        prices=GamePrices(**{kind: _number(row, field) for kind, field in price_fields().items()}),
        price_kinds=[kind for kind, field in price_fields().items() if field],
        price_updated=row.get(f.G_PRICE_UPDATED) if f.G_PRICE_UPDATED else None,
        cib_requires=cib_requires,
        upc=row.get(f.G_UPC) or "",
        cover_url=(row.get(f.G_COVER_URL) or None) if f.G_COVER_URL else None,
        completionator_url=(row.get(f.G_COMPLETIONATOR_URL) or None) if f.G_COMPLETIONATOR_URL else None,
        notes=row.get(f.G_NOTES) or "",
    )


def _completeness(
    sealed: bool, has_disc: bool, has_case: bool, has_manual: bool, cib_requires: list[str] | None
) -> str:
    if sealed:
        return "Sealed"
    present = [c for c, has in zip(CIB_COMPONENTS, (has_disc, has_case, has_manual)) if has]
    if not present:
        return "None"
    required = set(cib_requires) if cib_requires else set(CIB_COMPONENTS)
    if "Disc" in present and required.issubset(set(present)):
        return "Complete In Box"
    return " + ".join(present)


def _overall_quality(
    sealed: bool,
    has_disc: bool,
    disc_quality: int | None,
    has_case: bool,
    case_quality: int | None,
    has_manual: bool,
    manual_quality: int | None,
) -> float | None:
    if sealed:
        return None
    scores = [
        q
        for has, q in ((has_disc, disc_quality), (has_case, case_quality), (has_manual, manual_quality))
        if has and q is not None
    ]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 1)


def copy_row_to_out(row: dict, game_cib_requires: list[str] | None = None) -> CopyOut:
    status = row.get(f.C_STATUS)
    game = row.get(f.C_GAME) or []
    sealed = bool(row.get(f.C_SEALED))
    has_disc = bool(row.get(f.C_HAS_DISC))
    has_case = bool(row.get(f.C_HAS_CASE))
    has_manual = bool(row.get(f.C_HAS_MANUAL))
    disc_quality = int(row[f.C_DISC_QUALITY]) if row.get(f.C_DISC_QUALITY) is not None else None
    case_quality = int(row[f.C_CASE_QUALITY]) if row.get(f.C_CASE_QUALITY) is not None else None
    manual_quality = int(row[f.C_MANUAL_QUALITY]) if row.get(f.C_MANUAL_QUALITY) is not None else None

    return CopyOut(
        id=row["id"],
        copy_id=row.get(f.C_COPY_ID) or "",
        game_id=game[0]["id"] if game else None,
        game_title=game[0]["value"] if game else None,
        status=status["value"] if status else None,
        sealed=sealed,
        has_disc=has_disc,
        disc_quality=disc_quality,
        has_case=has_case,
        case_quality=case_quality,
        has_manual=has_manual,
        manual_quality=manual_quality,
        overall_quality=_overall_quality(
            sealed, has_disc, disc_quality, has_case, case_quality, has_manual, manual_quality
        ),
        completeness=_completeness(sealed, has_disc, has_case, has_manual, game_cib_requires),
        purchase_price=float(row[f.C_PURCHASE_PRICE]) if row.get(f.C_PURCHASE_PRICE) else None,
        purchase_date=row.get(f.C_PURCHASE_DATE),
        purchased_from=row.get(f.C_PURCHASED_FROM) or "",
        location=row.get(f.C_LOCATION) or "",
        notes=row.get(f.C_NOTES) or "",
        photo_url=_first_file_url(row.get(f.C_PHOTO)) if f.C_PHOTO else None,
    )


def _first_file_url(files: list[dict] | None) -> str | None:
    return files[0].get("url") if files else None


def sale_row_to_out(row: dict) -> SaleOut:
    sold_on = row.get(f.S_SOLD_ON)
    copy = row.get(f.S_COPY) or []
    net = row.get(f.S_NET)
    return SaleOut(
        id=row["id"],
        sale_id=row.get(f.S_SALE_ID) or "",
        copy_id=copy[0]["id"] if copy else None,
        copy_label=copy[0]["value"] if copy else None,
        sold_on=sold_on["value"] if sold_on else None,
        sale_date=row.get(f.S_SALE_DATE),
        sale_price=float(row[f.S_SALE_PRICE]) if row.get(f.S_SALE_PRICE) else None,
        fees=float(row[f.S_FEES]) if row.get(f.S_FEES) else None,
        shipping_cost=float(row[f.S_SHIPPING_COST]) if row.get(f.S_SHIPPING_COST) else None,
        net=float(net["value"]) if isinstance(net, dict) and net.get("value") is not None else net,
    )
