from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import require_auth
from app.baserow import field_ids as f
from app.baserow.client import BaserowError, baserow_client
from app.schemas import SaleCreate, SaleOut, sale_row_to_out

router = APIRouter(prefix="/api/sales", tags=["sales"], dependencies=[Depends(require_auth)])


@router.get("", response_model=list[SaleOut])
async def list_sales():
    rows = await baserow_client.list_rows(f.TABLE_SALES)
    sales = [sale_row_to_out(row) for row in rows]
    return sorted(sales, key=lambda s: s.sale_date or "", reverse=True)


@router.post("", response_model=SaleOut, status_code=201)
async def create_sale(body: SaleCreate):
    if body.sold_on not in f.SOLD_ON_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown sold_on: {body.sold_on}")

    values = {
        f.S_SALE_ID: body.sale_id,
        f.S_COPY: [body.copy_id],
        f.S_SOLD_ON: f.SOLD_ON_OPTIONS[body.sold_on],
        f.S_SALE_DATE: body.sale_date,
        f.S_SALE_PRICE: body.sale_price,
        f.S_FEES: body.fees,
        f.S_SHIPPING_COST: body.shipping_cost,
    }
    row = await baserow_client.create_row(f.TABLE_SALES, values)

    # Mark the sold copy's status as Sold.
    try:
        await baserow_client.update_row(f.TABLE_COPIES, body.copy_id, {f.C_STATUS: f.STATUS_OPTIONS["Sold"]})
    except BaserowError:
        pass

    return sale_row_to_out(row)


@router.delete("/{sale_id}", status_code=204)
async def delete_sale(sale_id: int):
    try:
        await baserow_client.delete_row(f.TABLE_SALES, sale_id)
    except BaserowError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Sale not found") from exc
        raise
