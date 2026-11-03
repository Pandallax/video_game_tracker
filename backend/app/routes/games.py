from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import require_auth
from app.baserow import field_ids as f
from app.baserow.client import BaserowError, baserow_client
from app.schemas import GameCreate, GameOut, GameUpdate, game_row_to_out, normalize_upc

router = APIRouter(prefix="/api/games", tags=["games"], dependencies=[Depends(require_auth)])


def _set_market_price(values: dict, price: float | None) -> None:
    values[f.G_MARKET_PRICE] = price
    if f.G_PRICE_UPDATED:
        values[f.G_PRICE_UPDATED] = date.today().isoformat()


def _set_cover(values: dict, cover_url: str) -> None:
    if not f.G_COVER_URL:
        raise HTTPException(status_code=400, detail="Cover URL field is not configured (see field_ids.py)")
    values[f.G_COVER_URL] = cover_url.strip()


def _cib_option_ids(components: list[str]) -> list[int]:
    unknown = [c for c in components if c not in f.CIB_COMPONENT_OPTIONS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown CIB component(s): {unknown}")
    return [f.CIB_COMPONENT_OPTIONS[c] for c in components]


@router.get("", response_model=list[GameOut])
async def list_games(platform: str | None = None):
    rows = await baserow_client.list_rows(f.TABLE_GAMES)
    games = [game_row_to_out(row) for row in rows]
    if platform:
        games = [g for g in games if g.platform == platform]
    return sorted(games, key=lambda g: g.title.lower())


@router.get("/by-upc/{upc}", response_model=GameOut)
async def get_game_by_upc(upc: str):
    target = normalize_upc(upc)
    if not target:
        raise HTTPException(status_code=400, detail="Invalid UPC")

    rows = await baserow_client.list_rows(f.TABLE_GAMES)
    for row in rows:
        row_upc = row.get(f.G_UPC) or ""
        if row_upc and normalize_upc(row_upc) == target:
            return game_row_to_out(row)
    raise HTTPException(status_code=404, detail="No game found for that UPC")


@router.post("", response_model=GameOut, status_code=201)
async def create_game(body: GameCreate):
    if body.platform not in f.PLATFORM_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {body.platform}")

    values = {
        f.G_TITLE: body.title,
        f.G_PLATFORM: f.PLATFORM_OPTIONS[body.platform],
        f.G_TARGET: body.target,
        f.G_CIB_REQUIRES: _cib_option_ids(body.cib_requires),
        f.G_UPC: body.upc,
        f.G_NOTES: body.notes,
    }
    if body.upgrade_to_id is not None:
        values[f.G_UPGRADE_TO] = [body.upgrade_to_id]
    if body.market_price is not None:
        _set_market_price(values, body.market_price)
    if body.cover_url:
        _set_cover(values, body.cover_url)

    row = await baserow_client.create_row(f.TABLE_GAMES, values)
    return game_row_to_out(row)


@router.patch("/{game_id}", response_model=GameOut)
async def update_game(game_id: int, body: GameUpdate):
    values: dict = {}
    if body.title is not None:
        values[f.G_TITLE] = body.title
    if body.platform is not None:
        if body.platform not in f.PLATFORM_OPTIONS:
            raise HTTPException(status_code=400, detail=f"Unknown platform: {body.platform}")
        values[f.G_PLATFORM] = f.PLATFORM_OPTIONS[body.platform]
    if body.target is not None:
        values[f.G_TARGET] = body.target
    if body.upgrade_to_id is not None:
        values[f.G_UPGRADE_TO] = [body.upgrade_to_id] if body.upgrade_to_id else []
    if "market_price" in body.model_fields_set:
        _set_market_price(values, body.market_price)
    if body.cib_requires is not None:
        values[f.G_CIB_REQUIRES] = _cib_option_ids(body.cib_requires)
    if body.upc is not None:
        values[f.G_UPC] = body.upc
    if body.cover_url is not None:
        _set_cover(values, body.cover_url)
    if body.notes is not None:
        values[f.G_NOTES] = body.notes

    try:
        row = await baserow_client.update_row(f.TABLE_GAMES, game_id, values)
    except BaserowError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Game not found") from exc
        raise
    return game_row_to_out(row)


@router.delete("/{game_id}", status_code=204)
async def delete_game(game_id: int):
    try:
        await baserow_client.delete_row(f.TABLE_GAMES, game_id)
    except BaserowError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Game not found") from exc
        raise
