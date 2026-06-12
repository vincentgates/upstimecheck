# UPS Time Reconciliation Tool

Personal tool for cross-checking UPS app clock-in/out times against the official UPS time system. Upload screenshots from both systems, OCR extracts the punch data, and the app shows a weekly view highlighting mismatches.

## Setup

### 1. Install Tesseract OCR

Tesseract is a system binary — it can't be pip-installed. Do this once per machine.

---

**Windows (development machine)**

1. Go to **https://github.com/UB-Mannheim/tesseract/wiki** and download the latest
   **64-bit Windows installer** (filename looks like `tesseract-ocr-w64-setup-*.exe`).
2. Run the installer. **Accept the default install path:**
   ```
   C:\Program Files\Tesseract-OCR\
   ```
   The app hard-codes this path for Windows. If you install somewhere else, update
   `pytesseract.pytesseract.tesseract_cmd` in `app/ocr.py` to match.
3. The "Add to PATH" checkbox is optional — the app sets the path in code.
   Checking it lets you run `tesseract --version` in a terminal to confirm the install.
4. Verify the install worked by running the debug script (after Python env is set up):
   ```bat
   python ocr_debug.py
   ```
   You should see the EXIF date, the raw OCR text, and two parsed punch dicts.

---

**macOS**
```bash
brew install tesseract
```

**Linux (Debian/Ubuntu / Heroku)**
```bash
sudo apt install tesseract-ocr
```
On Heroku, add `tesseract-ocr` to an `Aptfile` in the project root and use the
`heroku-buildpack-apt` buildpack — no code change needed, Linux finds it on PATH.

---

### 2. Set up the Python environment

**Windows**
```bat
# Delete .venv first if rebuilding from scratch
setup_env.bat
python run.py
```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r config/requirements.txt
python run.py
```

Then open http://localhost:3000.

The SQLite database (`database.db`) is created automatically on first run — no migration step needed.

## Project structure

```
upstimecheck/
├── app/
│   ├── __init__.py          # App factory (create_app)
│   ├── db.py                # SQLAlchemy instance + models
│   ├── ocr.py               # Tesseract wrapper — screenshot → punch dicts
│   ├── controllers/
│   │   ├── pages.py         # Static placeholder routes (/, /features, /faq)
│   │   ├── upload.py        # /upload — accepts screenshots, triggers OCR
│   │   └── calendar/
│   │       ├── calendar.py  # /cal weekly view route
│   │       └── models.py    # Date helpers
│   ├── templates/
│   │   ├── layouts/app.html # Base layout
│   │   ├── upload/          # Upload form
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
└── setup_env.bat            # Windows env bootstrap
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

## Why this tool exists

A time discrepancy between the UPS app punch and the official system means missed pay.
This tool detects those discrepancies and will auto-generate a **grievance form (PDF)**
the user can file to recover the difference.

**Upload workflow:** UPS operates Monday–Saturday. Upload both screenshot sources on Sunday
after the full week is complete. Cross-check pairs same-date punches across both sources
and flags any time differences.

**OCR confidence score:** Every punch record stores a confidence score (0–100%) from
Tesseract — how certain the engine was when reading the image. Photos of screens typically
score 60–80%. A low score means extracted times may be wrong. Use the Edit function to
correct them manually; the edit view shows the original image alongside editable fields.

## Current state (Phase 1, in progress)

- [x] Flask app boots, routes work
- [x] `database.db` creates with correct schema on first run
- [x] OCR pipeline — EXIF date, preprocessing, `Punched In/Out` parser, DB insert
- [x] Weekly calendar — live DB data, accordion + View modals, confidence %
- [ ] Cross-check logic — flag mismatches between `app` and `official` punches for same date
- [ ] Grievance form PDF — auto-generate on discrepancy (planned: WeasyPrint)
- [ ] Edit modal — original image + editable fields for low-confidence records

## Phase 2 (future)

Multi-user accounts with encrypted credentials. The schema reserves space for a `user_id` FK once that's added. No auth code exists yet — don't add it until Phase 1 is complete and stable.
