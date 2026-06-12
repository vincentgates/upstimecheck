# Project: UPS Time Reconciliation Tool

## Status
Phase 1 in progress. App boots, DB schema is live. OCR and real DB reads not yet wired.

## Stack
- Python / Flask 3.x
- SQLite (`database.db`) via Flask-SQLAlchemy — auto-created on first run
- OCR: pytesseract (not yet installed or wired — next Phase 1 task)
- Frontend: Bootstrap 5 accordion, Jinja2 templates

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
