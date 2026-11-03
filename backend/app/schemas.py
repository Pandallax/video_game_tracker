from pydantic import BaseModel, Field

from app.baserow import field_ids as f

CIB_COMPONENTS = ("Disc", "Case", "Manual")


class GameOut(BaseModel):
    id: int
    title: str
    platform: str | None
    target: bool
    upgrade_to_id: int | None
    market_price: float | None
    cib_requires: list[str]
    notes: str


class GameCreate(BaseModel):
    title: str
    platform: str
    target: bool = True
    upgrade_to_id: int | None = None
    market_price: float | None = None
    cib_requires: list[str] = list(CIB_COMPONENTS)
    notes: str = ""


class GameUpdate(BaseModel):
    title: str | None = None
    platform: str | None = None
    target: bool | None = None
    upgrade_to_id: int | None = None
    market_price: float | None = None
    cib_requires: list[str] | None = None
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
        market_price=float(row[f.G_MARKET_PRICE]) if row.get(f.G_MARKET_PRICE) else None,
        cib_requires=cib_requires,
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
    )


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
