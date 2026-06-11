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
**Phase 2 (later):** Multi-user accounts, encrypted credentials, `user_id` on punches.

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
