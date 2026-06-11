# UPS Time Reconciliation Tool

Personal tool for cross-checking UPS app clock-in/out times against the official UPS time system. Upload screenshots from both systems, OCR extracts the punch data, and the app shows a weekly view highlighting mismatches.

## Setup

Requires Python 3.x and Windows (uses `setup_env.bat`).

```bat
# From the project root — delete .venv first if rebuilding from scratch
setup_env.bat
python run.py
```

Then open http://localhost:3000.

`setup_env.bat` creates `.venv`, activates it, and installs `config/requirements.txt`. The SQLite database (`database.db`) is created automatically on first run — no migration step needed.

## Project structure

```
upstimecheck/
├── app/
│   ├── __init__.py          # App factory (create_app)
│   ├── db.py                # SQLAlchemy instance + models
│   ├── controllers/
│   │   ├── pages.py         # Static placeholder routes (/, /features, /faq)
│   │   └── calendar/
│   │       ├── calendar.py  # /cal weekly view route
│   │       └── models.py    # Date helpers (no DB access yet)
│   ├── templates/
│   │   ├── layouts/app.html # Base layout
│   │   ├── calendar/        # Weekly accordion view
│   │   ├── pages/           # Placeholder pages
│   │   └── partials/        # Navbar, head, footer, etc.
│   └── static/              # Fonts, images
├── config/
│   ├── development.py       # Dev config (DEBUG, HOST, PORT)
│   └── requirements.txt     # Python dependencies
├── tests/
├── database.db              # SQLite — auto-created, not committed
├── run.py                   # Entry point: python run.py
└── setup_env.bat            # Env bootstrap script
```

## Data schema

One table, `punches`, defined in `app/db.py`:

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `date` | DATE | |
| `time` | TIME | |
| `type` | VARCHAR(3) | `'in'` or `'out'` |
| `source` | VARCHAR(10) | `'app'` or `'official'` |
| `raw_ocr_text` | TEXT | Raw OCR output for debugging |
| `confidence` | FLOAT | OCR confidence score (0–1) |
| `created_at` | DATETIME | Set automatically on insert |

Cross-checking works by pairing rows with the same `date` and comparing `source='app'` vs `source='official'`.

## Current state (Phase 1, in progress)

- [x] Flask app boots, routes work
- [x] `database.db` creates with correct schema on first run
- [x] Weekly calendar view renders at `/cal` (accordion, prev/next week nav)
- [ ] OCR module — screenshot → `Punch` rows (pytesseract, not yet wired)
- [ ] Calendar view reads real data from DB (currently hardcoded placeholder)
- [ ] Cross-check logic — flag mismatches between app and official punches

## Phase 2 (future)

Multi-user accounts with encrypted credentials. The schema reserves space for a `user_id` FK once that's added. No auth code exists yet — don't add it until Phase 1 is complete and stable.
