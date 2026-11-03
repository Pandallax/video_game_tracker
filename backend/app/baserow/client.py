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

    async def list_rows(
        self, table_id: int, *, filters: dict[str, str] | None = None, size: int = 200
    ) -> list[dict]:
        params = {"size": size, "page": 1}
        if filters:
            params.update(filters)

        rows: list[dict] = []
        async with httpx.AsyncClient(timeout=15) as client:
            url = f"{self._base_url}/api/database/rows/table/{table_id}/"
            while url:
                resp = await client.get(url, headers=self._headers, params=params)
                if resp.status_code != 200:
                    raise BaserowError(resp.status_code, resp.text)
                data = resp.json()
                rows.extend(data["results"])
                url = data.get("next")
                params = None  # `next` already contains full query string
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
