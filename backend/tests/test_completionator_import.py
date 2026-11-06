import os

os.environ.setdefault("BASEROW_URL", "http://example.invalid")
os.environ.setdefault("BASEROW_API_TOKEN", "test")
os.environ.setdefault("APP_USERNAME", "test")
os.environ.setdefault("APP_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET", "test")

import asyncio

from fastapi.testclient import TestClient

from app.baserow import field_ids as f
from app.completionator import Entry, ImportOptions, parse_row, plan_updates, run_import
from app.main import app
from app.routes import imports

EDITIONS_FIELD = {"id": 99, "name": "Editions", "type": "single_select",
                  "select_options": [{"id": 501, "value": "Platinum Hits"}]}
FIELDS = [EDITIONS_FIELD]
OG = {"id": f.PLATFORM_OPTIONS["OG Xbox"], "value": "OG Xbox"}


def entry(title, edition="", loose=5.0, complete=9.5, new=40.0, cover="https://www.completionator.com/c.jpg"):
    return Entry(title=title, edition=edition, genre="", loose=loose, complete=complete, new=new,
                 release_type="Official Release", release_date="", url=f"https://www.completionator.com/Game/{title}",
                 cover_url=cover)


class FakeBaserow:
    def __init__(self, rows):
        self.rows = rows
        self.updated: list[dict] = []
        self.created: list[dict] = []

    async def list_rows(self, table_id):
        return self.rows

    async def list_fields(self, table_id):
        return FIELDS

    async def batch_update_rows(self, table_id, items):
        self.updated.extend(items)
        return items

    async def batch_create_rows(self, table_id, items):
        out = [{"id": 1000 + len(self.created) + i, **item} for i, item in enumerate(items)]
        self.created.extend(out)
        return out


def test_relative_cover_becomes_absolute():
    html = ('<td><img src="/Content/boxart/1.jpg"></td><td><a href="/Game/Details/1">Halo</a></td>'
            + "<td></td>" * 10)
    e = parse_row(html)
    assert e.cover_url == "https://www.completionator.com/Content/boxart/1.jpg"
    assert e.url == "https://www.completionator.com/Game/Details/1"


def test_plan_fills_only_empty_fields_by_default():
    rows = {1: {"id": 1, f.G_CIB_PRICE: "12.00", f.G_COVER_URL: "https://mine.example/halo.jpg"}}
    plan = plan_updates([(entry("Halo"), 1)], rows, FIELDS, ImportOptions(), "2026-11-06")
    u = plan.updates[1]
    assert u[f.G_LOOSE_PRICE] == 5.0 and u[f.G_SEALED_PRICE] == 40.0
    assert f.G_CIB_PRICE not in u  # already set
    assert f.G_COVER_URL not in u  # hand-entered cover kept
    assert u[f.G_PRICE_UPDATED] == "2026-11-06"
    assert plan.prices == 2 and plan.covers == 0


def test_plan_overwrite_and_unchanged_values():
    rows = {1: {"id": 1, f.G_CIB_PRICE: "9.50", f.G_LOOSE_PRICE: "4.00", f.G_COVER_URL: "old.jpg"}}
    opts = ImportOptions(overwrite_prices=True, overwrite_covers=True)
    plan = plan_updates([(entry("Halo"), 1)], rows, FIELDS, opts, "2026-11-06")
    u = plan.updates[1]
    assert f.G_CIB_PRICE not in u  # same value -> not rewritten
    assert u[f.G_LOOSE_PRICE] == 5.0
    assert u[f.G_COVER_URL] == "https://www.completionator.com/c.jpg"


def test_plan_editions_and_unknown_editions():
    rows = {1: {"id": 1}, 2: {"id": 2}}
    pairs = [(entry("Halo", edition="Platinum Hits"), 1), (entry("Fable", edition="Classics"), 2)]
    plan = plan_updates(pairs, rows, FIELDS, ImportOptions(set_prices=False), "2026-11-06")
    assert plan.updates[1]["field_99"] == 501
    assert plan.unknown_editions == {"Classics": 1}


def test_run_import_dry_run_writes_nothing():
    fake = FakeBaserow([{"id": 1, f.G_TITLE: "Halo", f.G_PLATFORM: OG}])
    s = asyncio.run(run_import(ImportOptions(dry_run=True, add_missing=True), client=fake,
                               entries=[entry("Halo"), entry("Fable")]))
    assert fake.updated == [] and fake.created == []
    assert s.matched == 1 and s.missing == ["Fable"] and s.added_games == 1
    assert s.games_updated == 1 and s.prices_set == 3 and s.covers_set == 1 and s.links_set == 1


def test_run_import_writes_and_adds_missing():
    fake = FakeBaserow([{"id": 1, f.G_TITLE: "Halo", f.G_PLATFORM: OG}])
    s = asyncio.run(run_import(ImportOptions(dry_run=False, add_missing=True), client=fake,
                               entries=[entry("Halo"), entry("Fable")]))
    assert [c[f.G_TITLE] for c in fake.created] == ["Fable"]
    assert {u["id"] for u in fake.updated} == {1, fake.created[0]["id"]}
    assert s.games_updated == 2 and s.added_games == 1


def test_import_endpoints_require_auth():
    client = TestClient(app)
    assert client.get("/api/import/completionator").status_code == 401
    assert client.post("/api/import/completionator", json={}).status_code == 401


def test_job_runs_in_background(monkeypatch):
    async def fake_run_import(options):
        return await run_import(options, client=FakeBaserow([{"id": 1, f.G_TITLE: "Halo", f.G_PLATFORM: OG}]),
                                entries=[entry("Halo")])

    monkeypatch.setattr(imports, "run_import", fake_run_import)

    async def scenario():
        job = await imports.start_import(ImportOptions())
        assert job.status == "running"
        await imports._task
        return await imports.import_status()

    done = asyncio.run(scenario())
    assert done.status == "done" and done.summary.matched == 1 and done.summary.dry_run


def test_job_reports_errors(monkeypatch):
    async def boom(options):
        raise RuntimeError("Completionator unreachable")

    monkeypatch.setattr(imports, "run_import", boom)

    async def scenario():
        await imports.start_import(ImportOptions())
        await imports._task
        return await imports.import_status()

    failed = asyncio.run(scenario())
    assert failed.status == "error" and "unreachable" in failed.error


def test_edition_whitespace_collapsed():
    html = '<td></td><td><a href="/Game/Details/1">Halo</a></td><td>Platinum  Hits</td>' + "<td></td>" * 9
    assert parse_row(html).edition == "Platinum Hits"
