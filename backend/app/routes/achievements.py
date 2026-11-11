from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import require_auth
from app.baserow import field_ids as f
from app.baserow.client import BaserowError, baserow_client
from app.schemas import (
    AchievementCreate,
    AchievementOut,
    AchievementUpdate,
    MythicStatus,
    achievement_row_to_out,
    mythic_status,
)

router = APIRouter(prefix="/api/achievements", tags=["achievements"], dependencies=[Depends(require_auth)])


async def _rows_for_game(game_id: int) -> list[dict]:
    rows = await baserow_client.list_rows(f.TABLE_ACHIEVEMENTS)
    return [row for row in rows if any(g.get("id") == game_id for g in (row.get(f.A_GAME) or []))]


@router.get("", response_model=list[AchievementOut])
async def list_achievements(game_id: int):
    rows = await _rows_for_game(game_id)
    return [achievement_row_to_out(row) for row in rows]


@router.get("/mythic-status", response_model=MythicStatus)
async def get_mythic_status(game_id: int):
    rows = await _rows_for_game(game_id)
    achievements = [achievement_row_to_out(row) for row in rows]
    return mythic_status(game_id, achievements)


@router.post("", response_model=AchievementOut, status_code=201)
async def create_achievement(body: AchievementCreate):
    values = {
        f.A_NAME: body.name,
        f.A_GAME: [body.game_id],
        f.A_UNLOCKED: body.unlocked,
        f.A_REQUIRED_FOR_MYTHIC: body.required_for_mythic,
        f.A_NOTES: body.notes,
    }
    row = await baserow_client.create_row(f.TABLE_ACHIEVEMENTS, values)
    return achievement_row_to_out(row)


@router.patch("/{achievement_id}", response_model=AchievementOut)
async def update_achievement(achievement_id: int, body: AchievementUpdate):
    values: dict = {}
    if body.name is not None:
        values[f.A_NAME] = body.name
    if body.unlocked is not None:
        values[f.A_UNLOCKED] = body.unlocked
    if body.required_for_mythic is not None:
        values[f.A_REQUIRED_FOR_MYTHIC] = body.required_for_mythic
    if body.notes is not None:
        values[f.A_NOTES] = body.notes

    try:
        row = await baserow_client.update_row(f.TABLE_ACHIEVEMENTS, achievement_id, values)
    except BaserowError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Achievement not found") from exc
        raise
    return achievement_row_to_out(row)


@router.delete("/{achievement_id}", status_code=204)
async def delete_achievement(achievement_id: int):
    try:
        await baserow_client.delete_row(f.TABLE_ACHIEVEMENTS, achievement_id)
    except BaserowError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Achievement not found") from exc
        raise
