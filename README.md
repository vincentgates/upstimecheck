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
| `image_path` | VARCHAR(255) | Saved screenshot filename (served from `uploads/processed/`) |
| `scheduled_time` | TIME | Company-confirmed shift start, OCR-scraped from terminal screen |
| `daily_total_minutes` | INTEGER | Total time worked per the system screenshot (in minutes) |
| `created_at` | DATETIME | Set automatically on insert |

Cross-checking works by pairing rows with the same `date` and comparing `source='app'` vs `source='official'`.

### Daily total logic

Each upload may include a "Daily Total" field printed on the terminal screen — this is stored as `daily_total_minutes` (the system's own calculation). The app independently calculates `punch_out − punch_in` (using scheduled start time as the floor if you punched in early) and compares. A mismatch flags a discrepancy.

### Early punch — future grievance opportunity

If your app punch-in time is earlier than your `scheduled_time`, the company's system does **not** count those early minutes toward your pay — your paid time starts at the scheduled start, not when you actually arrived. However, the screenshot from the UPS app is timestamped evidence that you were on the clock before the scheduled time. A future "File Grievance (Early Punch)" feature will let you generate a form for those missed early minutes using this proof.

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

---

## UPS Business Rules

These are the contractual and operational rules that govern how this tool interprets
punch data, calculates pay, and determines when a grievance is warranted. Every
calculation and discrepancy flag in the app is built around these rules.

### 1. Work week schedule

- **The operational week runs Sunday through Saturday.**
- **Sunday is typically a no-service day.** Package delivery does not operate on Sunday
  in most hubs. It is the default day off and the recommended day to upload the previous
  week's screenshots for cross-checking.
- **Saturday evening shifts** may start late and cross into early Sunday morning (e.g.,
  a shift starting 11:00 PM Saturday). Those hours belong to the **Saturday** date for
  pay purposes — the EXIF timestamp on the screenshot is the authoritative date, not the
  clock-hour of the following calendar day.
- The weekly view in this app spans **Sunday → Saturday** to reflect this schedule.

### 2. Part-time overtime threshold — 5 hours per day

UPS part-time employees (the primary users of this tool) are covered under the
Teamsters / IBT contract. The overtime rule for part-timers is:

> **Any time worked beyond 5 hours in a single workday is paid at 1.5× the hourly rate.**

This is a **daily** threshold, not a weekly one. Full-time employees have a different
threshold — this tool is scoped to part-time only.

| Hours worked | Pay rate |
|---|---|
| Up to 5:00 (300 min) | Regular (1×) |
| Every minute after 5:00 | Overtime (1.5×) |

The grievance form will use this to calculate the **monetary value** of a discrepancy.
A 15-minute shortfall at the end of a 6-hour shift is worth more than the same 15 minutes
at the start, because those minutes fall in the overtime window.

### 3. Scheduled start time is required on every upload

The **scheduled start time** — the company-confirmed time your shift begins — must be
visible on the screenshot you upload. The OCR pipeline reads it from the terminal screen
(look for "Scheduled" or "Sched" on the Punch Out Summary).

Why it matters:
- Paid time **begins at the scheduled start**, not at your actual punch-in time (unless
  you can prove early work — see Rule 4).
- The overtime 5-hour window counts from the scheduled start, not from actual punch-in.
- Without a scheduled time, the daily total calculation and overtime split cannot be
  correctly determined.

If the scheduled time is missing from an image (low angle, cut off, etc.), enter it
manually in the Edit modal — it is as important as the punch times themselves.

### 4. Early punch policy — proof required for early pay

**Clocking in early does NOT automatically entitle you to pay from that early time.**

The company's system will begin counting your pay from your scheduled start time,
regardless of when you physically punched in. This is by design and is within the
company's contractual rights — **unless you can prove you were actively working
before the scheduled start.**

The rule, stated plainly:

| Situation | Result |
|---|---|
| Punched in early, **no proof of work** | Scheduled start is valid; no grievance applies |
| Punched in early, **with proof of work** | Early minutes are grievable; file for the difference |

**What counts as proof?**
The UPS app screenshot itself serves as timestamped evidence that you were on the
premises and clocked in before the scheduled start. If the app shows an early punch
and work was actively being performed (e.g., you were in the facility, on the belt,
scanning packages), that screenshot is your exhibit A.

A future "File Grievance (Early Punch)" feature in this tool will generate a separate
form specifically for early-punch situations, attaching the screenshot as proof. Until
then, the calendar view flags the early punch, shows the delta, and prompts you to
decide whether to file.

**What this means for the cross-check:**
- If `app.punch_in < scheduled_time`, the system flags it as an early punch.
- The daily total is still calculated from `scheduled_time` as the floor (not actual
  punch-in) unless the early punch has been manually marked as proven.
- A discrepancy between the system's daily total and the calculated total will still
  appear — it is your prompt to decide whether the evidence supports filing.

---

## Current state (Phase 1, in progress)

- [x] Flask app boots, routes work
- [x] `database.db` creates with correct schema on first run
- [x] OCR pipeline — EXIF date, preprocessing, `Punched In/Out` parser, DB insert
- [x] Scheduled time + daily total OCR-scraped and stored per punch
- [x] Weekly calendar — live DB data, accordion + View modals, confidence %
- [x] Edit modal — original image on the left, editable time fields on the right
- [x] Cross-check logic — flags punch time mismatches and daily total mismatches
- [x] Early punch detection — flagged in calendar when `app.punch_in < scheduled_time`
- [ ] Grievance form PDF — WeasyPrint (planned); "File Grievance" button is placeholder
- [ ] Early punch grievance form — separate from standard discrepancy form
- [ ] Overtime split on grievance form — show regular vs 1.5× portion of disputed time

## Phase 2 (future)

Multi-user accounts with encrypted credentials. The schema reserves space for a `user_id` FK once that's added. No auth code exists yet — don't add it until Phase 1 is complete and stable.
