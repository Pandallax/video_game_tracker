import asyncio
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.deps import require_auth
from app.baserow import field_ids as f
from app.baserow.client import BaserowError, baserow_client
from app.baserow.game_fields import edition_field, edition_write_value
from app.schemas import (
    EditionOptions,
    GameCreate,
    GameOut,
    GamePage,
    GamePrices,
    GameUpdate,
    changed_price_fields,
    game_row_to_out,
    normalize_upc,
    price_fields,
)

router = APIRouter(prefix="/api/games", tags=["games"], dependencies=[Depends(require_auth)])


def _set_prices(values: dict, prices: GamePrices, current_row: dict | None = None) -> None:
    """Write the price kinds that were sent (null clears one), and stamp Price
    updated if any of them differs from `current_row` (the game as it is now;
    None for a new game)."""
    sent = prices.model_fields_set
    if not sent:
        return
    fields = price_fields()
    missing = sorted(kind for kind in sent if not fields[kind])
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Price field(s) not configured in Baserow (see field_ids.py): {', '.join(missing)}",
        )
    new_prices = {fields[kind]: getattr(prices, kind) for kind in sent}
    values.update(new_prices)
    if f.G_PRICE_UPDATED and changed_price_fields(current_row, new_prices):
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


async def _edition_key() -> str | None:
    fld = await edition_field()
    return fld.key if fld else None


async def _set_edition(values: dict, edition: str) -> None:
    fld = await edition_field()
    if fld is None:
        if edition.strip():
            raise HTTPException(status_code=400, detail='No "Editions" field on the Games table in Baserow')
        return
    try:
        values[fld.key] = edition_write_value(fld, edition)
    except ValueError:
        # Maybe the option was just added in Baserow -- re-read once.
        fld = await edition_field(refresh=True)
        try:
            values[fld.key] = edition_write_value(fld, edition)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown edition {edition!r}; add it as an option on the Editions field in Baserow",
            ) from None


@router.get("/editions", response_model=EditionOptions)
async def list_editions():
    fld = await edition_field(refresh=True)
    if fld is None:
        return EditionOptions(configured=False, options=[], free_text=False)
    return EditionOptions(configured=True, options=list(fld.options), free_text=not fld.is_select)


def search_params(search: str = "", platform: str | None = None) -> dict[str, str]:
    """Baserow query params for a Games page: sorted by title, optionally
    narrowed by platform and a search. An all-digit search matches UPCs (so a
    scanned or typed barcode works); anything else matches the title."""
    params = {"order_by": f.G_TITLE}
    if platform:
        if platform not in f.PLATFORM_OPTIONS:
            raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")
        params[f"filter__{f.G_PLATFORM}__single_select_equal"] = str(f.PLATFORM_OPTIONS[platform])
    search = search.strip()
    if search:
        digits = search.replace(" ", "").replace("-", "")
        if digits.isdigit() and len(digits) >= 4:
            params[f"filter__{f.G_UPC}__contains"] = normalize_upc(digits)
        else:
            params[f"filter__{f.G_TITLE}__contains"] = search
    return params


@router.get("/page", response_model=GamePage)
async def list_games_page(
    search: str = "",
    platform: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=48, ge=1, le=200),
):
    """One page of games for the Games page (fast first paint + search)."""
    (rows, total), edition_key = await asyncio.gather(
        baserow_client.list_rows_page(f.TABLE_GAMES, page=page, size=size, params=search_params(search, platform)),
        _edition_key(),
    )
    return GamePage(items=[game_row_to_out(row, edition_key) for row in rows], total=total, page=page, size=size)


@router.get("", response_model=list[GameOut])
async def list_games(platform: str | None = None):
    rows, edition_key = await asyncio.gather(baserow_client.list_rows(f.TABLE_GAMES), _edition_key())
    games = [game_row_to_out(row, edition_key) for row in rows]
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
            return game_row_to_out(row, await _edition_key())
    raise HTTPException(status_code=404, detail="No game found for that UPC")


@router.get("/{game_id}", response_model=GameOut)
async def get_game(game_id: int):
    row = await baserow_client.get_row(f.TABLE_GAMES, game_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return game_row_to_out(row, await _edition_key())


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
    if body.edition.strip():
        await _set_edition(values, body.edition)
    if body.prices is not None:
        _set_prices(values, body.prices)
    if body.cover_url:
        _set_cover(values, body.cover_url)

    row = await baserow_client.create_row(f.TABLE_GAMES, values)
    return game_row_to_out(row, await _edition_key())


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
    if body.edition is not None:
        await _set_edition(values, body.edition)
    if body.prices is not None and body.prices.model_fields_set:
        current = await baserow_client.get_row(f.TABLE_GAMES, game_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Game not found")
        _set_prices(values, body.prices, current)
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
    return game_row_to_out(row, await _edition_key())


@router.delete("/{game_id}", status_code=204)
async def delete_game(game_id: int):
    try:
        await baserow_client.delete_row(f.TABLE_GAMES, game_id)
    except BaserowError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Game not found") from exc
        raise
