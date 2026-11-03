# Video Game Tracker

Tracks progress toward a complete OG Xbox / Xbox 360 collection, plus Xbox One
and Series X|S purchases. Duplicates/upgrades get marked "For Sale" and sold
through eBay (and other marketplaces) as a separate product line from the
TCG Dashboard's card business.

Runs alongside `tcg-dashboard` on the same VM (10.10.11.45) as a fully
separate app: its own repo, systemd service, port, and Baserow database/token,
so changes here never touch the card-selling dashboard.

## Setup

1. Copy `.env.example` to `.env` and fill in `BASEROW_API_TOKEN`, `APP_USERNAME`,
   `APP_PASSWORD`, `SESSION_SECRET`.
2. Backend:
   ```
   cd backend
   python3 -m venv .venv
   ./.venv/bin/pip install -e ".[dev]"
   ./.venv/bin/uvicorn app.main:app --reload --port 8000
   ```
3. Frontend:
   ```
   cd frontend
   npm install
   npm run dev
   ```
   Open http://localhost:5173

## Tests

```
cd backend
./.venv/bin/pytest
```

## Data model (Baserow database "Game Tracker", id 339)

- **Games** (table 1374): Title, Platform, Target, Upgrade to (self-link),
  Market price, Price updated (date, stamped by the app whenever Market price
  changes), CIB Requires, Cover URL, Completionator URL, Notes. Platinum Hits / other editions get their own row with
  `Upgrade to` pointing at the base edition; `Target` is off unless that
  specific printing is the one being chased.
- **Copies** (table 1375): Copy ID, Game (link), Status (Collection / For Sale
  / Sold), Condition, Purchase price, Purchase date, Purchased from, Location,
  Notes, Photo (file). First copy of a title goes to Collection; duplicates go For Sale.
- **Sales** (table 1376): Sale ID, Copy (link), Sold on, Sale date, Sale
  price, Fees, Shipping cost, Net (formula).

Completion stats only count `Collection` copies of `Target`-flagged games.

Cover URL is filled in by hand: click a game's thumbnail on the Games page
and paste an image link (or edit the field in Baserow). Each game also links to a PriceCharting search for that
title and console.

`scripts/import_completionator.py` compares saved pages of a Completionator
checklist (no export exists, so save each page from the browser) against the
Games table, and can add missing games/editions, fill Market price from the
checklist's loose/complete/new prices, and store each game's Completionator
link. It only writes a report unless given flags; see its docstring.

Copies can have their own photo (Copies page: click the thumbnail). Uploads
are resized to at most 1600px and re-encoded as WebP at 85% quality
(`backend/app/photos.py`) before being stored in Baserow; that photo is shown
in place of the game's cover art wherever the copy appears.

See `scripts/discover_baserow.py` to re-dump the current field/table IDs if
the schema changes (`backend/app/baserow/field_ids.py` is hand-synced from it).

## Deploy (on 10.10.11.45)

- systemd unit `video-game-tracker-backend.service` runs uvicorn on
  `127.0.0.1:8001`.
- nginx serves `frontend/dist` and proxies `/api/` on a dedicated port
  (`:8081`), separate from tcg-dashboard's `:80`. That server block needs
  `client_max_body_size 25m;` so phone photos can be uploaded (nginx's
  default limit is 1 MB).
- `scripts/deploy.sh` runs from cron every 5 minutes, polling `origin/main`
  and restarting/rebuilding only what changed.
