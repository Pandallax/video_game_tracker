import asyncio
import re

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.auth.deps import require_auth
from app.baserow import field_ids as f
from app.baserow.client import BaserowError, baserow_client
from app.photos import MAX_UPLOAD_BYTES, PhotoError, to_webp
from app.schemas import CopyCreate, CopyOut, CopyUpdate, copy_row_to_out

router = APIRouter(prefix="/api/copies", tags=["copies"], dependencies=[Depends(require_auth)])


def _cib_requires(game_row: dict | None) -> list[str] | None:
    if game_row is None:
        return None
    return [opt["value"] for opt in (game_row.get(f.G_CIB_REQUIRES) or [])]


def _platform(game_row: dict | None) -> str | None:
    platform = (game_row or {}).get(f.G_PLATFORM)
    return platform["value"] if platform else None


def _game_id(copy_row: dict) -> int | None:
    linked = copy_row.get(f.C_GAME) or []
    return linked[0]["id"] if linked else None


async def _out(copy_row: dict, game_row: dict | None = None) -> CopyOut:
    if game_row is None and (gid := _game_id(copy_row)):
        game_row = await baserow_client.get_row(f.TABLE_GAMES, gid)
    return copy_row_to_out(copy_row, _cib_requires(game_row), _platform(game_row))


_TRAILING_NUMBER = re.compile(r"^(.*?)(\d+)$")


def next_copy_id(existing: list[str]) -> str:
    """Continue the highest-numbered Copy ID series (keeping its prefix and
    zero padding), or start at C-0001."""
    best: tuple[int, str, int] | None = None  # (number, prefix, width)
    for cid in existing:
        m = _TRAILING_NUMBER.match((cid or "").strip())
        if m and (best is None or int(m.group(2)) > best[0]):
            best = (int(m.group(2)), m.group(1), len(m.group(2)))
    if best is None:
        return "C-0001"
    number, prefix, width = best
    return f"{prefix}{number + 1:0{width}d}"


def default_status(game_id: int, copy_rows: list[dict]) -> str:
    """First copy of a game goes to the collection; duplicates go up for sale."""
    for row in copy_rows:
        status = (row.get(f.C_STATUS) or {}).get("value")
        if _game_id(row) == game_id and status == "Collection":
            return "For Sale"
    return "Collection"


@router.get("", response_model=list[CopyOut])
async def list_copies(status: str | None = None, game_id: int | None = None):
    copy_rows, game_rows = await asyncio.gather(
        baserow_client.list_rows(f.TABLE_COPIES), baserow_client.list_rows(f.TABLE_GAMES)
    )
    games_by_id = {g["id"]: g for g in game_rows}

    copies = []
    for row in copy_rows:
        game = games_by_id.get(_game_id(row))
        copies.append(copy_row_to_out(row, _cib_requires(game), _platform(game)))

    if status:
        copies = [c for c in copies if c.status == status]
    if game_id:
        copies = [c for c in copies if c.game_id == game_id]
    return copies


@router.post("", response_model=CopyOut, status_code=201)
async def create_copy(body: CopyCreate):
    if body.status is not None and body.status not in f.STATUS_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown status: {body.status}")

    game, copy_rows = await asyncio.gather(
        baserow_client.get_row(f.TABLE_GAMES, body.game_id), baserow_client.list_rows(f.TABLE_COPIES)
    )
    if game is None:
        raise HTTPException(status_code=400, detail="Game not found")

    copy_id = body.copy_id.strip()
    if not copy_id:
        copy_id = next_copy_id([r.get(f.C_COPY_ID) or "" for r in copy_rows])
    elif any((r.get(f.C_COPY_ID) or "").strip().lower() == copy_id.lower() for r in copy_rows):
        raise HTTPException(status_code=400, detail=f"Copy ID {copy_id} is already used")
    status = body.status or default_status(body.game_id, copy_rows)

    # A sealed copy has every part; quality only applies to parts you have.
    sealed = body.sealed
    values = {
        f.C_COPY_ID: copy_id,
        f.C_GAME: [body.game_id],
        f.C_STATUS: f.STATUS_OPTIONS[status],
        f.C_SEALED: sealed,
        f.C_HAS_DISC: body.has_disc and not sealed,
        f.C_DISC_QUALITY: body.disc_quality if body.has_disc and not sealed else None,
        f.C_HAS_CASE: body.has_case and not sealed,
        f.C_CASE_QUALITY: body.case_quality if body.has_case and not sealed else None,
        f.C_HAS_MANUAL: body.has_manual and not sealed,
        f.C_MANUAL_QUALITY: body.manual_quality if body.has_manual and not sealed else None,
        f.C_PURCHASE_PRICE: body.purchase_price,
        f.C_PURCHASE_DATE: body.purchase_date or None,
        f.C_PURCHASED_FROM: body.purchased_from,
        f.C_LOCATION: body.location,
        f.C_NOTES: body.notes,
    }

    row = await baserow_client.create_row(f.TABLE_COPIES, values)
    return await _out(row, game)


# CopyUpdate field -> Baserow field. Fields sent as null are cleared.
_UPDATE_FIELDS = {
    "sealed": f.C_SEALED,
    "has_disc": f.C_HAS_DISC,
    "disc_quality": f.C_DISC_QUALITY,
    "has_case": f.C_HAS_CASE,
    "case_quality": f.C_CASE_QUALITY,
    "has_manual": f.C_HAS_MANUAL,
    "manual_quality": f.C_MANUAL_QUALITY,
    "purchase_price": f.C_PURCHASE_PRICE,
    "purchase_date": f.C_PURCHASE_DATE,
    "purchased_from": f.C_PURCHASED_FROM,
    "location": f.C_LOCATION,
    "notes": f.C_NOTES,
}
_PART_QUALITY = {"has_disc": "disc_quality", "has_case": "case_quality", "has_manual": "manual_quality"}


def update_values(body: CopyUpdate) -> dict:
    """Baserow values for the fields that were sent. null clears nullable
    fields; un-checking a part also clears its quality."""
    sent = body.model_fields_set
    values: dict = {}
    if "status" in sent and body.status is not None:
        if body.status not in f.STATUS_OPTIONS:
            raise HTTPException(status_code=400, detail=f"Unknown status: {body.status}")
        values[f.C_STATUS] = f.STATUS_OPTIONS[body.status]
    for name, key in _UPDATE_FIELDS.items():
        if name not in sent:
            continue
        value = getattr(body, name)
        if value is None and name in ("sealed", "has_disc", "has_case", "has_manual"):
            continue  # booleans can't be cleared
        if value is None and name in ("purchased_from", "location", "notes"):
            value = ""
        if name == "purchase_date" and value == "":
            value = None
        values[key] = value
    for part, quality in _PART_QUALITY.items():
        if part in sent and getattr(body, part) is False:
            values[_UPDATE_FIELDS[quality]] = None
    if "sealed" in sent and body.sealed:
        for part, quality in _PART_QUALITY.items():
            values[_UPDATE_FIELDS[part]] = False
            values[_UPDATE_FIELDS[quality]] = None
    return values


@router.patch("/{copy_id}", response_model=CopyOut)
async def update_copy(copy_id: int, body: CopyUpdate):
    return await _save_copy(copy_id, update_values(body))


async def _save_copy(copy_id: int, values: dict) -> CopyOut:
    try:
        row = await baserow_client.update_row(f.TABLE_COPIES, copy_id, values)
    except BaserowError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Copy not found") from exc
        raise

    return await _out(row)


def _photo_field() -> str:
    if not f.C_PHOTO:
        raise HTTPException(status_code=400, detail="Photo field is not configured (see field_ids.py)")
    return f.C_PHOTO


@router.put("/{copy_id}/photo", response_model=CopyOut)
async def upload_photo(copy_id: int, file: UploadFile):
    """Replace the copy's photo. The image is re-encoded to WebP before it's stored."""
    field = _photo_field()
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Photo is larger than {MAX_UPLOAD_BYTES // 1_000_000} MB")
    try:
        webp = to_webp(content)
    except PhotoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    uploaded = await baserow_client.upload_file(f"copy-{copy_id}.webp", webp, "image/webp")
    return await _save_copy(copy_id, {field: [{"name": uploaded["name"]}]})


@router.delete("/{copy_id}/photo", response_model=CopyOut)
async def delete_photo(copy_id: int):
    return await _save_copy(copy_id, {_photo_field(): []})


@router.delete("/{copy_id}", status_code=204)
async def delete_copy(copy_id: int):
    try:
        await baserow_client.delete_row(f.TABLE_COPIES, copy_id)
    except BaserowError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Copy not found") from exc
        raise
