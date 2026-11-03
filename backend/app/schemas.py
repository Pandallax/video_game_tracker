from pydantic import BaseModel

from app.baserow import field_ids as f


class GameOut(BaseModel):
    id: int
    title: str
    platform: str | None
    target: bool
    upgrade_to_id: int | None
    target_price: float | None
    notes: str


class GameCreate(BaseModel):
    title: str
    platform: str
    target: bool = True
    upgrade_to_id: int | None = None
    target_price: float | None = None
    notes: str = ""


class GameUpdate(BaseModel):
    title: str | None = None
    platform: str | None = None
    target: bool | None = None
    upgrade_to_id: int | None = None
    target_price: float | None = None
    notes: str | None = None


class CopyOut(BaseModel):
    id: int
    copy_id: str
    game_id: int | None
    game_title: str | None
    status: str | None
    condition: str | None
    purchase_price: float | None
    purchase_date: str | None
    purchased_from: str
    location: str
    notes: str


class CopyCreate(BaseModel):
    copy_id: str
    game_id: int
    status: str = "Collection"
    condition: str | None = None
    purchase_price: float | None = None
    purchase_date: str | None = None
    purchased_from: str = ""
    location: str = ""
    notes: str = ""


class CopyUpdate(BaseModel):
    status: str | None = None
    condition: str | None = None
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
    return GameOut(
        id=row["id"],
        title=row.get(f.G_TITLE) or "",
        platform=platform["value"] if platform else None,
        target=bool(row.get(f.G_TARGET)),
        upgrade_to_id=upgrade[0]["id"] if upgrade else None,
        target_price=float(row[f.G_TARGET_PRICE]) if row.get(f.G_TARGET_PRICE) else None,
        notes=row.get(f.G_NOTES) or "",
    )


def copy_row_to_out(row: dict) -> CopyOut:
    status = row.get(f.C_STATUS)
    condition = row.get(f.C_CONDITION)
    game = row.get(f.C_GAME) or []
    return CopyOut(
        id=row["id"],
        copy_id=row.get(f.C_COPY_ID) or "",
        game_id=game[0]["id"] if game else None,
        game_title=game[0]["value"] if game else None,
        status=status["value"] if status else None,
        condition=condition["value"] if condition else None,
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
