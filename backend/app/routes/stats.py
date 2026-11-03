from fastapi import APIRouter, Depends

from app.auth.deps import require_auth
from app.baserow import field_ids as f
from app.baserow.client import baserow_client
from app.schemas import GameOut, PlatformStats, game_row_to_out

router = APIRouter(prefix="/api/stats", tags=["stats"], dependencies=[Depends(require_auth)])


async def _owned_game_ids() -> set[int]:
    """Game ids with at least one Copy row whose Status is Collection."""
    rows = await baserow_client.list_rows(f.TABLE_COPIES)
    owned: set[int] = set()
    for row in rows:
        status = row.get(f.C_STATUS)
        if not status or status["value"] != "Collection":
            continue
        for game in row.get(f.C_GAME) or []:
            owned.add(game["id"])
    return owned


@router.get("/completion", response_model=list[PlatformStats])
async def completion_by_platform():
    rows = await baserow_client.list_rows(f.TABLE_GAMES)
    games = [game_row_to_out(row) for row in rows]
    owned = await _owned_game_ids()

    result = []
    for platform in f.PLATFORM_OPTIONS:
        targeted = [g for g in games if g.platform == platform and g.target]
        owned_count = sum(1 for g in targeted if g.id in owned)
        result.append(PlatformStats(platform=platform, owned=owned_count, total=len(targeted)))
    return result


@router.get("/missing", response_model=list[GameOut])
async def missing_games(platform: str | None = None):
    """Targeted games with no Collection copy yet."""
    rows = await baserow_client.list_rows(f.TABLE_GAMES)
    games = [game_row_to_out(row) for row in rows]
    owned = await _owned_game_ids()

    missing = [g for g in games if g.target and g.id not in owned]
    if platform:
        missing = [g for g in missing if g.platform == platform]
    return sorted(missing, key=lambda g: g.title.lower())
