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
Phase 1 in progress. OCR pipeline live, calendar reads DB. Cross-check logic next.

## End goal — why this tool exists
A time discrepancy between the UPS app punch and the official system = missed pay.
The cross-check logic detects those discrepancies and the app will auto-generate a
**grievance form (PDF)** the user can file to recover the difference.

- PDF generation not yet implemented. Planned library: WeasyPrint (HTML → PDF).
- The form will include: date, app time, official time, delta in minutes, employee name.
- Trigger: "File Grievance" button on a discrepancy row. Download/print only — no auto-submit.

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
