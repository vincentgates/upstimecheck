# Project: UPS Time Reconciliation Tool

## Deployment target — READ THIS FIRST

**Production runs on Linux (Heroku or similar PaaS). Development runs on Windows.**
This is a hard constraint that applies to every code change, forever.

Rules that follow from this:
- **Never hardcode Windows paths.** No `C:\...`, no `r'C:\Program Files\...'` anywhere in
  application code. Use `platform.system()` guards or environment variables instead.
- **No Windows-only binaries.** Any system dependency (e.g. Tesseract) must be installable
  on Linux via `apt` / a Heroku buildpack. Document it in `Aptfile` or `Procfile` notes.
- **Tesseract path** is set conditionally in `app/ocr.py` — Windows gets the hardcoded
  installer path; Linux finds it on `PATH` automatically (no override needed).
- **Secret key, DB URL, and any credentials** must come from environment variables before
  any production push. The current hardcoded key in `app/__init__.py` is dev-only.
- **SQLite is fine for now.** Heroku's ephemeral filesystem means the DB resets on dyno
  restart — acceptable for Phase 1 testing. Phase 2 will need a persistent store
  (PostgreSQL via `heroku-postgres` add-on, or an attached volume).

When adding any new system-level dependency, ask: *does this work on a fresh Ubuntu dyno?*

## Status
Phase 1 in progress. OCR pipeline live, calendar reads DB, cross-check logic live.
Scheduled time + daily total tracking added. Grievance form PDF is next.

## End goal — why this tool exists
A time discrepancy between the UPS app punch and the official system = missed pay.
The cross-check logic detects those discrepancies and the app will auto-generate a
**grievance form (PDF)** the user can file to recover the difference.

- PDF generation not yet implemented. Planned library: WeasyPrint (HTML → PDF).
- The form will include: date, app time, official time, delta in minutes, employee name.
- Trigger: "File Grievance" button on a discrepancy row. Download/print only — no auto-submit.

### Early punch grievance (future)
If `app.punch_in < scheduled_time`, the company won't pay those early minutes — paid time
starts at `scheduled_time`. But the app screenshot is timestamped proof that the worker
was present before the shift start. A future "File Grievance (Early Punch)" feature should
use that screenshot as exhibit A on an early-punch form. Track this with `scheduled_time`
(already in DB) and compare against `app` source `punch_in`.

## UPS Business Logic — READ BEFORE WRITING CALCULATION CODE

These rules come directly from the UPS Teamsters / IBT part-time contract and
operational practice. Every calculation, flag, and grievance form must honor them.
Do not deviate from these rules without explicit instruction.

### Work week and schedule

- The operational week is **Sunday through Saturday**.
- **Sunday is typically a no-service day** — no deliveries, usually no shifts.
  It is the natural upload day for the prior Mon–Sat week.
- **Saturday evening shifts** can run past midnight into early Sunday. The punch date
  for those records is **Saturday** — determined by EXIF timestamp, never by
  the clock hour of the following calendar day. This is not an edge case; it is normal.
- The weekly calendar view should span Sunday → Saturday to match the operational week.

### Part-time overtime threshold

> Part-time employees earn **1.5× pay for every minute worked beyond 5 hours (300 minutes)
> in a single workday.**

This is a **daily** threshold, not weekly. Do not apply a weekly hour total.

```
regular_minutes  = min(actual_worked_minutes, 300)
overtime_minutes = max(actual_worked_minutes - 300, 0)
total_pay        = (regular_minutes * rate) + (overtime_minutes * rate * 1.5)
```

Where `actual_worked_minutes = max(punch_out, scheduled_time) - effective_start`.
The 5-hour clock starts at `effective_start`, which is `max(punch_in, scheduled_time)`
unless the early punch has been proven (see below).

When a discrepancy exists, always report **which side of the 5-hour line the disputed
minutes fall on** — missed overtime minutes are worth 1.5× and must be flagged separately
on the grievance form.

### Scheduled time is mandatory

- `scheduled_time` must be present for any meaningful pay or overtime calculation.
- The OCR pipeline reads it via `_SCHED_RE` from the terminal screen ("Scheduled HH:MM").
- If OCR misses it, the Edit modal must be used to fill it in manually.
- **Never calculate overtime or effective daily total without a known `scheduled_time`.**
  Show a warning in the UI if it is missing rather than silently calculating with a wrong floor.

### Early punch rules — two distinct states

**State A — Early punch, no proof (default):**
- `punch_in < scheduled_time`, and no proof has been attached or marked.
- Treat `effective_start = scheduled_time`.
- The early minutes do NOT count toward worked time.
- Do not open a grievance for the early delta — it is within company rights.
- Flag it in the UI as informational only ("punched in X min early — no proof on file").

**State B — Early punch, proof present:**
- `punch_in < scheduled_time`, AND the UPS app screenshot constitutes proof that work
  was being performed before the scheduled start.
- Treat `effective_start = punch_in` (the actual clock-in time).
- The early minutes DO count toward worked time and are grievable.
- The grievance form for an early punch is a **separate form** from the standard
  punch-time discrepancy form. It should include: date, scheduled start, actual punch-in,
  early delta in minutes, and the screenshot as exhibit A.

The DB does not yet have a `proof_status` column for early punches — add one when
building the early punch grievance flow. Until then, all early punches are treated as
State A (no proof assumed) and flagged for manual review.

### Daily total mismatch interpretation

The `daily_total_minutes` field comes from the terminal screen (what the system says you
worked). The calculated total is derived from punch times with the scheduled-time floor
applied. If they differ:

- **System total > calculated total:** The system is crediting you more time than the
  punch math shows — unusual, worth noting but not grievable.
- **System total < calculated total:** You worked more than the system credited —
  this IS grievable. The delta (in minutes) should be reported with its overtime
  split (how many of those minutes fall past the 5-hour mark).

## Upload workflow (UPS schedule)
UPS operates Monday–Saturday. Sunday is the ideal upload day:
- Upload **both** screenshot sources after the full Mon–Sat week is complete.
- `source='app'`      → UPS handheld/terminal clock-in screenshots (taken at punch time).
- `source='official'` → Punch Out Summary screen (the system being cross-referenced).
- Cross-check pairs same-date punches across sources and flags time differences.

## Stack
- Python / Flask 3.x
- SQLite (`database.db`) via Flask-SQLAlchemy — auto-created on first run
- OCR: pytesseract + Tesseract binary
- PDF (planned): WeasyPrint — HTML/CSS → PDF, Linux-compatible, pip-installable
- Frontend: Bootstrap 5 accordion + modals, Jinja2 templates, SASS via npm

## Phases
**Phase 1 (current):** Single-user, no auth. Goal: OCR → DB → weekly view → cross-check.
**Phase 2 (later):** Multi-user accounts, encrypted credentials, user-scoped uploads.

Do not add auth or user tables until Phase 1 is stable.

## Branching
Git-flow style. Work on `develop`, feature branches off `develop`, releases cut into `main`.

## Data model
Defined in `app/db.py`. One table for now:

```
punches: id, date, time, type ('in'|'out'), source ('app'|'official'),
         raw_ocr_text, confidence, created_at
```

When Phase 2 arrives, add `user_id` FK — don't restructure the rest of the table.

## Phase 2 architecture notes

**This app is essentially an image gallery with OCR metadata.** Keep that mental model —
it clarifies every design decision below.

### Upload storage
Store image files on disk, never in the DB. Path: `uploads/<user_id>/<filename>`.
Downsample with Pillow before saving — phone screenshots are 3–5 MB, OCR doesn't
need full resolution. Discard the original after downsampling.

### Two-layer data model
Upload records and punch records are separate concerns linked by a FK:

```
users:   id, email, password_hash, created_at

uploads: id, user_id (FK), filepath, source ('app'|'official'),
         uploaded_at, ocr_json (TEXT)

punches: id, upload_id (FK), user_id (FK), date, time,
         type ('in'|'out'), source, confidence, created_at
```

- `uploads.ocr_json` — raw Tesseract key-value output stored as a JSON string.
  Debug artifact only; the app never queries inside it. SQLite handles JSON fine
  with `json_extract()` if needed later.
- `punches` rows are derived from an upload. One upload → many punches.
- Both tables carry `user_id` so punches can be queried without joining uploads.

### Why SQLite is still the right call
SQLite is not a heavy relational system — it's a single file with SQL and built-in
JSON support. It's the right fit for this workload. No need to switch engines.
If it ever outgrows SQLite, Flask-SQLAlchemy makes migrating to PostgreSQL
straightforward with minimal code changes.

### File serving
Serve uploaded images through a Flask route (`/uploads/<user_id>/<filename>`) so
files stay outside the `static/` folder and access can be gated per-user later.

## Conventions

**DB access:** All queries go through `app/db.py`. No raw SQL scattered in controllers.
Do not import `db` directly in templates or helpers — go through the controller layer.

**Models:** Flask-SQLAlchemy ORM. Add new models to `app/db.py`.

**Blueprints:** One blueprint per feature area under `app/controllers/`. Register in `app/__init__.py`.

**Schema changes:** Use `db.create_all()` for now (Phase 1). Switch to Flask-Migrate
when the schema stabilizes and needs version-controlled migrations.

**No dead imports:** Don't leave unused blueprints or packages wired in. Auth routes
(`/login`, `/register`, `/forgot`) exist as templates but the blueprint is NOT registered.

**Setup:** Delete `.venv` and rerun `setup_env.bat` for a clean environment rebuild.
The `.venv` directory and `database.db` are not committed.

**Secret key:** Currently hardcoded in `app/__init__.py` — acceptable for local single-user use.
Move to env var before any networked or multi-user deployment.
