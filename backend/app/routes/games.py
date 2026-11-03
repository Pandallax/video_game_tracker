from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import require_auth
from app.baserow import field_ids as f
from app.baserow.client import BaserowError, baserow_client
from app.schemas import GameCreate, GameOut, GameUpdate, game_row_to_out

router = APIRouter(prefix="/api/games", tags=["games"], dependencies=[Depends(require_auth)])


@router.get("", response_model=list[GameOut])
async def list_games(platform: str | None = None):
    rows = await baserow_client.list_rows(f.TABLE_GAMES)
    games = [game_row_to_out(row) for row in rows]
    if platform:
        games = [g for g in games if g.platform == platform]
    return sorted(games, key=lambda g: g.title.lower())


@router.post("", response_model=GameOut, status_code=201)
async def create_game(body: GameCreate):
    if body.platform not in f.PLATFORM_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {body.platform}")

    values = {
        f.G_TITLE: body.title,
        f.G_PLATFORM: f.PLATFORM_OPTIONS[body.platform],
        f.G_TARGET: body.target,
        f.G_TARGET_PRICE: body.target_price,
        f.G_NOTES: body.notes,
    }
    if body.upgrade_to_id is not None:
        values[f.G_UPGRADE_TO] = [body.upgrade_to_id]

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
    if body.target_price is not None:
        values[f.G_TARGET_PRICE] = body.target_price
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
