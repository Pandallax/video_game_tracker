from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import require_auth
from app.baserow import field_ids as f
from app.baserow.client import BaserowError, baserow_client
from app.schemas import CopyCreate, CopyOut, CopyUpdate, copy_row_to_out

router = APIRouter(prefix="/api/copies", tags=["copies"], dependencies=[Depends(require_auth)])


@router.get("", response_model=list[CopyOut])
async def list_copies(status: str | None = None, game_id: int | None = None):
    rows = await baserow_client.list_rows(f.TABLE_COPIES)
    copies = [copy_row_to_out(row) for row in rows]
    if status:
        copies = [c for c in copies if c.status == status]
    if game_id:
        copies = [c for c in copies if c.game_id == game_id]
    return copies


@router.post("", response_model=CopyOut, status_code=201)
async def create_copy(body: CopyCreate):
    if body.status not in f.STATUS_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown status: {body.status}")
    if body.condition is not None and body.condition not in f.CONDITION_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown condition: {body.condition}")

    values = {
        f.C_COPY_ID: body.copy_id,
        f.C_GAME: [body.game_id],
        f.C_STATUS: f.STATUS_OPTIONS[body.status],
        f.C_PURCHASE_PRICE: body.purchase_price,
        f.C_PURCHASE_DATE: body.purchase_date,
        f.C_PURCHASED_FROM: body.purchased_from,
        f.C_LOCATION: body.location,
        f.C_NOTES: body.notes,
    }
    if body.condition is not None:
        values[f.C_CONDITION] = f.CONDITION_OPTIONS[body.condition]

    row = await baserow_client.create_row(f.TABLE_COPIES, values)
    return copy_row_to_out(row)


@router.patch("/{copy_id}", response_model=CopyOut)
async def update_copy(copy_id: int, body: CopyUpdate):
    values: dict = {}
    if body.status is not None:
        if body.status not in f.STATUS_OPTIONS:
            raise HTTPException(status_code=400, detail=f"Unknown status: {body.status}")
        values[f.C_STATUS] = f.STATUS_OPTIONS[body.status]
    if body.condition is not None:
        if body.condition not in f.CONDITION_OPTIONS:
            raise HTTPException(status_code=400, detail=f"Unknown condition: {body.condition}")
        values[f.C_CONDITION] = f.CONDITION_OPTIONS[body.condition]
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
    return copy_row_to_out(row)


@router.delete("/{copy_id}", status_code=204)
async def delete_copy(copy_id: int):
    try:
        await baserow_client.delete_row(f.TABLE_COPIES, copy_id)
    except BaserowError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Copy not found") from exc
        raise
