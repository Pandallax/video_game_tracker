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
  per-condition prices -- Loose Price (disc only), CIB Price (complete in
  box), Sealed Price, Box Only Price, Manual Only Price --
  Price updated (date, stamped by the app when a saved edit changes any
  price -- edits made directly in Baserow don't update it), CIB Requires (Disc/Case/Manual -- which components count as
  "Complete In Box" for this title), UPC, Cover URL, Completionator URL,
  Notes. Platinum Hits / other editions get their own row with `Upgrade to`
  pointing at the base edition; `Target` is off unless that specific printing
  is the one being chased.
- **Copies** (table 1375): Copy ID, Game (link), Status (Collection / For Sale
  / Sold), Sealed, Has Disc / Disc Quality, Has Case / Case Quality, Has
  Manual / Manual Quality (1-10 each), Purchase price, Purchase date,
  Purchased from, Location, Notes, Photo (file). Completeness ("Complete In
  Box", "Disc + Case", etc.) and overall quality are computed from the
  components present, checked against the linked game's CIB Requires -- not
  stored directly. First copy of a title goes to Collection; duplicates go
  For Sale.
- **Sales** (table 1376): Sale ID, Copy (link), Sold on, Sale date, Sale
  price, Fees, Shipping cost, Net (formula).

CIB Price was originally the single "Market price" field (same field id).
The Copies page shows an estimated value per copy: the Sealed or CIB
price when it is sealed or complete, otherwise the loose + box-only +
manual-only prices for the parts it has, capped at CIB.

Completion stats only count `Collection` copies of `Target`-flagged games.

The Dashboard has a "Scan UPC" button that opens the phone camera
(`@zxing/browser`) to look up a game by its barcode and jump straight to
adding a copy. Camera access needs a secure context, which is why the VM
serves `:8081` over TLS (see Deploy below).

Games has an "Editions" field (single select, found by name, so options can
be added in Baserow at any time): blank is the normal release, otherwise e.g.
"Platinum Hits". Platinum Hits games get a silver/platinum card and badge;
other editions get a purple one. This is a label on the row, separate from
the long-standing convention of giving an edition its own "Title (Edition)"
row with `Upgrade to` pointing at the base release -- both are used together.

The Game List page loads 48 games at a time (sorted by title, via
`GET /api/games/page`) and fetches more as you scroll, so it opens quickly
however big the catalog gets. The search box filters on the server: text
matches titles, 4+ digits match UPCs. Pages that still need every game
(Copies, Dashboard) fetch Baserow's pages in parallel.

The Game List page has a Table / Cards toggle (remembered per browser). Cards show
large cover art, title, platform, edition, the CIB price up front and the
other prices underneath.

Game List rows are read-only; click Edit on a row to change its title,
platform, target, prices, UPC, CIB requirements or cover image URL, then Save
(or Cancel). Saving sends only what changed, and Price updated is set to
today only if one of the prices actually changed.

Cover URL can be filled in by hand (Edit the game on the Game List page and paste
an image link, or edit the field in Baserow) or automatically from
Completionator (see below). Each game also links to a PriceCharting search
for that title and console.

**Import from Completionator** (Game List → Imports page, `/games/imports`): fetches Completionator's
OG Xbox NTSC-U physical checklist directly from its public, robots.txt-allowed
checklist endpoint (the same call the checklist page makes; a browser "Save
Page As" can't capture it because the table loads after the page), matches it
to the Games table by title + edition, and fills Loose / CIB / Sealed prices,
box art for that exact printing, Editions and Completionator links. By default
it only fills empty fields; "Replace existing" options overwrite. **Preview**
shows the counts without writing; **Run import** writes. It runs as a
background job on the backend (`backend/app/completionator.py`,
`app/routes/imports.py`), so the page just polls for the result. Checklist
editions that aren't options on the Editions field are listed so you can add
them in Baserow and run again. Only covers OG Xbox -- Completionator has no
360/One/Series X checklist yet.

`scripts/import_completionator.py` is the same import from the command line
(on the VM: `cd backend && ./.venv/bin/python ../scripts/import_completionator.py --all`);
it also writes completionator_report.csv. See its docstring for the flags.

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
- `:8081` is TLS (self-signed cert at `/etc/nginx/ssl/video-game-tracker.*`,
  10-year validity, IP SAN for `10.10.11.45`) because the UPC scanner's
  camera access requires a secure context. Browsers warn on first visit;
  accept the warning once per device. Regenerate with:
  `openssl req -x509 -newkey rsa:2048 -keyout video-game-tracker.key -out video-game-tracker.crt -days 3650 -nodes -subj "/CN=10.10.11.45" -addext "subjectAltName=IP:10.10.11.45"`
- `scripts/deploy.sh` runs from cron every 5 minutes, polling `origin/main`
  and restarting/rebuilding only what changed.
