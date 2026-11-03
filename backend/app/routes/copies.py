from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import require_auth
from app.baserow import field_ids as f
from app.baserow.client import BaserowError, baserow_client
from app.schemas import CopyCreate, CopyOut, CopyUpdate, copy_row_to_out

router = APIRouter(prefix="/api/copies", tags=["copies"], dependencies=[Depends(require_auth)])


async def _cib_requires_for_game(game_id: int) -> list[str] | None:
    row = await baserow_client.get_row(f.TABLE_GAMES, game_id)
    if row is None:
        return None
    return [opt["value"] for opt in (row.get(f.G_CIB_REQUIRES) or [])]


async def _cib_requires_by_game_id(game_ids: set[int]) -> dict[int, list[str]]:
    result = {}
    for game_id in game_ids:
        cib = await _cib_requires_for_game(game_id)
        if cib is not None:
            result[game_id] = cib
    return result


@router.get("", response_model=list[CopyOut])
async def list_copies(status: str | None = None, game_id: int | None = None):
    rows = await baserow_client.list_rows(f.TABLE_COPIES)

    game_ids = {gid for row in rows if (gid := ((row.get(f.C_GAME) or [None])[0] or {}).get("id"))}
    cib_by_game = await _cib_requires_by_game_id(game_ids)

    copies = []
    for row in rows:
        linked = row.get(f.C_GAME) or []
        gid = linked[0]["id"] if linked else None
        copies.append(copy_row_to_out(row, cib_by_game.get(gid)))

    if status:
        copies = [c for c in copies if c.status == status]
    if game_id:
        copies = [c for c in copies if c.game_id == game_id]
    return copies


@router.post("", response_model=CopyOut, status_code=201)
async def create_copy(body: CopyCreate):
    if body.status not in f.STATUS_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown status: {body.status}")

    values = {
        f.C_COPY_ID: body.copy_id,
        f.C_GAME: [body.game_id],
        f.C_STATUS: f.STATUS_OPTIONS[body.status],
        f.C_SEALED: body.sealed,
        f.C_HAS_DISC: body.has_disc,
        f.C_DISC_QUALITY: body.disc_quality,
        f.C_HAS_CASE: body.has_case,
        f.C_CASE_QUALITY: body.case_quality,
        f.C_HAS_MANUAL: body.has_manual,
        f.C_MANUAL_QUALITY: body.manual_quality,
        f.C_PURCHASE_PRICE: body.purchase_price,
        f.C_PURCHASE_DATE: body.purchase_date,
        f.C_PURCHASED_FROM: body.purchased_from,
        f.C_LOCATION: body.location,
        f.C_NOTES: body.notes,
    }

    row = await baserow_client.create_row(f.TABLE_COPIES, values)
    cib_requires = await _cib_requires_for_game(body.game_id)
    return copy_row_to_out(row, cib_requires)


@router.patch("/{copy_id}", response_model=CopyOut)
async def update_copy(copy_id: int, body: CopyUpdate):
    values: dict = {}
    if body.status is not None:
        if body.status not in f.STATUS_OPTIONS:
            raise HTTPException(status_code=400, detail=f"Unknown status: {body.status}")
        values[f.C_STATUS] = f.STATUS_OPTIONS[body.status]
    if body.sealed is not None:
        values[f.C_SEALED] = body.sealed
    if body.has_disc is not None:
        values[f.C_HAS_DISC] = body.has_disc
    if body.disc_quality is not None:
        values[f.C_DISC_QUALITY] = body.disc_quality
    if body.has_case is not None:
        values[f.C_HAS_CASE] = body.has_case
    if body.case_quality is not None:
        values[f.C_CASE_QUALITY] = body.case_quality
    if body.has_manual is not None:
        values[f.C_HAS_MANUAL] = body.has_manual
    if body.manual_quality is not None:
        values[f.C_MANUAL_QUALITY] = body.manual_quality
    if body.purchase_price is not None:
        values[f.C_PURCHASE_PRICE] = body.purchase_price
    if body.purchase_date is not None:
        values[f.C_PURCHASE_DATE] = body.purchase_date
    if body.purchased_from is not None:
        values[f.C_PURCHASED_FROM] = body.purchased_from
    if body.location is not None:
        values[f.C_LOCATION] = body.location
    if body.notes is not None:
        values[f.C_NOTES] = body.notes

    try:
        row = await baserow_client.update_row(f.TABLE_COPIES, copy_id, values)
    except BaserowError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Copy not found") from exc
        raise

    linked = row.get(f.C_GAME) or []
    cib_requires = await _cib_requires_for_game(linked[0]["id"]) if linked else None
    return copy_row_to_out(row, cib_requires)


@router.delete("/{copy_id}", status_code=204)
async def delete_copy(copy_id: int):
    try:
        await baserow_client.delete_row(f.TABLE_COPIES, copy_id)
    except BaserowError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Copy not found") from exc
        raise
