import asyncio

import httpx

from app.config import settings


class BaserowError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Baserow error {status_code}: {detail}")


class BaserowClient:
    def __init__(self):
        self._base_url = settings.baserow_url.rstrip("/")
        self._headers = {"Authorization": f"Token {settings.baserow_api_token}"}

    async def list_rows_page(
        self,
        table_id: int,
        *,
        page: int = 1,
        size: int = 200,
        params: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> tuple[list[dict], int]:
        """One page of rows plus the total matching count. `params` are passed
        straight to Baserow (filter__field_X__type, order_by, search, ...)."""
        query = {"size": size, "page": page, **(params or {})}
        url = f"{self._base_url}/api/database/rows/table/{table_id}/"
        if client is None:
            async with httpx.AsyncClient(timeout=15) as own_client:
                resp = await own_client.get(url, headers=self._headers, params=query)
        else:
            resp = await client.get(url, headers=self._headers, params=query)
        if resp.status_code == 404 and page > 1:
            return [], 0  # past the last page
        if resp.status_code != 200:
            raise BaserowError(resp.status_code, resp.text)
        data = resp.json()
        return data["results"], data.get("count", len(data["results"]))

    async def list_rows(
        self, table_id: int, *, filters: dict[str, str] | None = None, size: int = 200
    ) -> list[dict]:
        """Every row. Reads the first page to learn the total, then fetches the
        remaining pages concurrently instead of one after another."""
        async with httpx.AsyncClient(timeout=30) as client:
            rows, count = await self.list_rows_page(table_id, size=size, params=filters, client=client)
            pages = -(-count // size)  # ceil
            if pages > 1:
                rest = await asyncio.gather(
                    *(
                        self.list_rows_page(table_id, page=n, size=size, params=filters, client=client)
                        for n in range(2, pages + 1)
                    )
                )
                for page_rows, _ in rest:
                    rows.extend(page_rows)
        return rows

    async def create_row(self, table_id: int, field_values: dict) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self._base_url}/api/database/rows/table/{table_id}/",
                headers=self._headers,
                json=field_values,
            )
        if resp.status_code not in (200, 201):
            raise BaserowError(resp.status_code, resp.text)
        return resp.json()

    async def batch_create_rows(self, table_id: int, rows: list[dict]) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self._base_url}/api/database/rows/table/{table_id}/batch/",
                headers=self._headers,
                json={"items": rows},
            )
        if resp.status_code not in (200, 201):
            raise BaserowError(resp.status_code, resp.text)
        return resp.json()["items"]

    async def batch_update_rows(self, table_id: int, rows: list[dict]) -> list[dict]:
        """Each item must include "id" plus the field values to change (max 200 per call)."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(
                f"{self._base_url}/api/database/rows/table/{table_id}/batch/",
                headers=self._headers,
                json={"items": rows},
            )
        if resp.status_code != 200:
            raise BaserowError(resp.status_code, resp.text)
        return resp.json()["items"]

    async def list_fields(self, table_id: int) -> list[dict]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self._base_url}/api/database/fields/table/{table_id}/", headers=self._headers)
        if resp.status_code != 200:
            raise BaserowError(resp.status_code, resp.text)
        return resp.json()

    async def upload_file(self, filename: str, content: bytes, content_type: str) -> dict:
        """Upload to Baserow's user-file storage; set a file field to [{"name": result["name"]}]."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self._base_url}/api/user-files/upload-file/",
                headers=self._headers,
                files={"file": (filename, content, content_type)},
            )
        if resp.status_code != 200:
            raise BaserowError(resp.status_code, resp.text)
        return resp.json()

    async def get_row(self, table_id: int, row_id: int) -> dict | None:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self._base_url}/api/database/rows/table/{table_id}/{row_id}/",
                headers=self._headers,
            )
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            raise BaserowError(resp.status_code, resp.text)
        return resp.json()

    async def update_row(self, table_id: int, row_id: int, field_values: dict) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.patch(
                f"{self._base_url}/api/database/rows/table/{table_id}/{row_id}/",
                headers=self._headers,
                json=field_values,
            )
        if resp.status_code not in (200, 201):
            raise BaserowError(resp.status_code, resp.text)
        return resp.json()

    async def delete_row(self, table_id: int, row_id: int) -> None:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.delete(
                f"{self._base_url}/api/database/rows/table/{table_id}/{row_id}/",
                headers=self._headers,
            )
        if resp.status_code != 204:
            raise BaserowError(resp.status_code, resp.text)

    async def batch_delete_rows(self, table_id: int, row_ids: list[int]) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self._base_url}/api/database/rows/table/{table_id}/batch-delete/",
                headers=self._headers,
                json={"items": row_ids},
            )
        if resp.status_code != 204:
            raise BaserowError(resp.status_code, resp.text)


baserow_client = BaserowClient()
