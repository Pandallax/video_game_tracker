"""Run the Completionator import from the app (Dashboard), as a background job
so a slow fetch can't time out the request. One job at a time; the latest
job's state is kept in memory (it resets when the backend restarts)."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import require_auth
from app.completionator import ImportOptions, ImportSummary, run_import

router = APIRouter(prefix="/api/import", tags=["import"], dependencies=[Depends(require_auth)])
log = logging.getLogger(__name__)


class ImportJob(BaseModel):
    status: Literal["idle", "running", "done", "error"] = "idle"
    options: ImportOptions | None = None
    started_at: str | None = None
    finished_at: str | None = None
    summary: ImportSummary | None = None
    error: str | None = None


_job = ImportJob()
_task: asyncio.Task | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _run(options: ImportOptions) -> None:
    global _job
    try:
        summary = await run_import(options)
        _job = _job.model_copy(update={"status": "done", "summary": summary, "finished_at": _now()})
    except Exception as exc:  # noqa: BLE001 -- surface any failure to the Dashboard
        log.exception("Completionator import failed")
        _job = _job.model_copy(update={"status": "error", "error": str(exc) or type(exc).__name__, "finished_at": _now()})


@router.get("/completionator", response_model=ImportJob)
async def import_status():
    return _job


@router.post("/completionator", response_model=ImportJob, status_code=202)
async def start_import(options: ImportOptions):
    global _job, _task
    if _job.status == "running":
        raise HTTPException(status_code=409, detail="An import is already running")
    _job = ImportJob(status="running", options=options, started_at=_now())
    _task = asyncio.create_task(_run(options))
    return _job
