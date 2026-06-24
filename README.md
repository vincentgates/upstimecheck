# UPS Time Reconciliation Tool

Personal tool for cross-checking UPS app clock-in/out times against the official UPS time system. Upload screenshots from both systems, OCR extracts the punch data, and the app shows a weekly view highlighting mismatches — building toward grievance form generation.

---

## Setup

### 1. Install Tesseract OCR

Tesseract is a system binary — it can't be pip-installed. Do this once per machine.

**Windows (development)**

1. Download the latest 64-bit installer from https://github.com/UB-Mannheim/tesseract/wiki
2. Run the installer. Accept the default path: `C:\Program Files\Tesseract-OCR\`
   The app hardcodes this path for Windows via `platform.system()` guard.
3. Verify after Python env is set up:
   ```bat
   python ocr_debug.py app uploads/test/YOUR_IMAGE.jpg
   ```

**macOS**
```bash
brew install tesseract
```

**Linux / Heroku**
```bash
sudo apt install tesseract-ocr
```
On Heroku: add `tesseract-ocr` to an `Aptfile` and use `heroku-buildpack-apt`.

---

### 2. Set up the Python environment

**Windows**
```bat
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

Open http://localhost:3000. The SQLite database creates automatically on first run.

---

## Project structure

```
upstimecheck/
├── app/
│   ├── __init__.py           # App factory (create_app)
│   ├── db.py                 # SQLAlchemy models
│   ├── ocr_app.py            # OCR pipeline — UPS app photos
│   ├── ocr_official.py       # OCR pipeline — official system screenshots
│   ├── controllers/
│   │   ├── pages.py          # Static routes (home, features)
│   │   ├── upload.py         # /upload — routes to correct OCR pipeline
│   │   └── calendar/
│   │       ├── calendar.py   # /cal weekly view
│   │       └── models.py     # Date helpers
│   ├── templates/
│   └── static/
├── config/
│   ├── development.py
│   └── requirements.txt
├── ocr_debug.py              # CLI debug harness — test both OCR pipelines
├── database.db               # SQLite — auto-created, not committed
├── run.py
└── setup_env.bat             # Windows env bootstrap
```

---

## OCR pipelines

Two separate pipelines, one per upload source. The naming convention used throughout the app:

- **UPS app photos** — phone photos of the UPS handheld terminal screen
- **Official system screenshots** — screenshots of the UPS weekly time web portal

### app/ocr_app.py — UPS app photos
Handles phone photos of the UPS handheld terminal "Punch Out Summary" screen.
One image → one day → one DB record.

**Preprocessing (tuned 2026-06-23 against Samsung Galaxy 8000×6000px photos):**
- Crop: 2% left, 10% top, 98% right, 68% bottom — removes bezel and EXIT button
- Downscale to 1600px wide
- Grayscale + 1.2× contrast boost (intentionally conservative — no threshold)

The time values appear in teal boxes with white text. Heavy preprocessing destroys
them. The 1.2× contrast is the correct setting — do not increase it.

### app/ocr_official.py — official system screenshots
Handles screenshots of the UPS weekly time portal (Microsoft/UPS.com).
One image → one week → multiple DB records (one per worked day).

Times are stored as decimal hours in the portal: `4.17 = 4h 10m`.
`_decimal_hours_to_time()` handles conversion.

**Upsert behavior:** reimporting a screenshot for a week that already has data will update existing records, not duplicate them. Newer import always wins. This is by design — official system data is the authoritative source.

---

## Debug harness

`ocr_debug.py` is the primary tool for testing and tuning OCR output.

```bash
# Test app pipeline
python ocr_debug.py app uploads/test/IMAGE.jpg

# Test official pipeline
python ocr_debug.py official uploads/test/IMAGE.jpg

# Test with gold standard comparison
python ocr_debug.py app uploads/test/IMAGE.jpg "Punched In 03:43 Punched Out 09:17"
```

**Output (per punch record):**
1. RAW OCR BLOCK — the raw text stored in `raw_ocr_text` for that day block
2. PARSED FIELDS — the dict that would be inserted into the DB
3. CONFIDENCE score (page-level, same across all records)
4. GOLD STANDARD CHECK — token match % (optional, 80%+ is good)

**To visually inspect the preprocessed image:**
```bash
python -c "from app.ocr_app import _preprocess; _preprocess('path/to/img.jpg').save('debug_preprocessed.png')"
```

---

## Data schema

### app_punches
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `date` | DATE | From EXIF metadata |
| `punch_in` | TIME | |
| `punch_out` | TIME | |
| `scheduled_time` | TIME | OCR-scraped from terminal screen |
| `daily_total_minutes` | INTEGER | System's own total, in minutes |
| `raw_ocr_text` | TEXT | Raw Tesseract output for debugging |
| `confidence` | FLOAT | OCR confidence 0.0–1.0 |
| `image_path` | VARCHAR | Saved screenshot path |
| `created_at` | DATETIME | |

### official_punches
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `date` | DATE | |
| `punch_in` | TIME | Converted from decimal hours |
| `punch_out` | TIME | Converted from decimal hours |
| `pay_code` | VARCHAR | As-is from portal (e.g. `PAY ACTUAL`, `No Card`, `TEMP STS CHANGE - PAY ACTUAL`) |
| `gross_pay` | FLOAT | |
| `pay_rate` | FLOAT | |
| `daily_total_minutes` | INTEGER | |
| `corrected` | BOOLEAN | True if start time had asterisk (*) |
| `raw_ocr_text` | TEXT | |
| `confidence` | FLOAT | |
| `created_at` | DATETIME | |

### discrepancy_notes *(planned — Phase 1.5)*
Stores written statements and proof images for flagged punch discrepancies.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `date` | DATE | Links to punch date |
| `can_prove` | BOOLEAN | Did the user assert they can prove the discrepancy? |
| `statement` | TEXT | Written statement |
| `proof_image_path` | VARCHAR | Optional uploaded proof photo |
| `created_at` | DATETIME | |

### user_profile *(planned — Phase 1.5)*
Hard-coded or single-row table. Required before grievance forms can be generated.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `name` | VARCHAR | |
| `employee_id` | VARCHAR | |
| `ups_center` | VARCHAR | |
| `job_title` | VARCHAR | |

---

## UPS Business Rules

### Work week
- Operational week: **Sunday through Saturday**
- Sunday = no service day, ideal upload day for prior week
- Saturday late shifts crossing midnight = still **Saturday** date (EXIF is authoritative)

### Part-time overtime — 5 hours/day
> Every minute worked beyond 5 hours (300 min) in a single day = **1.5× pay**

```
regular_minutes  = min(worked_minutes, 300)
overtime_minutes = max(worked_minutes - 300, 0)
```

### Scheduled time
Required for all calculations. Never calculate overtime without it.
If missing from OCR, enter manually in the Edit modal.

### Early punch
- Early punch + no proof → `effective_start = scheduled_time` (company's right)
- Early punch + proof → `effective_start = punch_in` (grievable)
- The UPS app photo IS the proof for an early punch grievance

---

## Phases

### Phase 1 — Data In ✅ Complete (RC5)
Flask app, dual OCR pipelines (refactored RC5), weekly calendar view, cross-check logic, edit modal, early punch detection, confidence scoring. OCR parser handles all known UPS pay code formats including TCD entries.

---

### Phase 1.5 — Polish & User Foundation

**Data & Backend**
- [ ] Upsert on reimport — EXIF date match updates existing record instead of duplicating
- [ ] Official system screenshot always upserts — newer import always wins
- [ ] Bulk upload — accept an array of UPS app photos at once and process as a batch
- [ ] Single-day official screenshot support — pipeline currently expects full week view; add support for single-day screenshots
- [ ] Discrepancy proof flow — when a mismatch is flagged, allow user to record yes/no "can prove it", written statement, and optional proof photo upload; stored in DB for Phase 2 grievance use
- [ ] User profile — name, employee ID, UPS center, etc.; hard-coded or simple DB table; required before grievances can be generated

**UI — Visual Design**
- [ ] Navbar — high contrast, vector UPS logo or custom branded logo
- [ ] Bootstrap Icons — integrate globally; replace all arrows with `bi-chevron-left` / `bi-chevron-right` on week navigation
- [ ] Color coding by source — UPS app photo data gets blue tinge; official system data gets yellow tinge (mirrors UPS.com branding)
- [ ] Confidence score — demote from primary UI; backend/debug concern only

**Calendar / Weekly View**
- [ ] Green checkmark on accordion date = both UPS app photo AND official screenshot present
- [ ] Yellow warning on accordion date = only one source uploaded (incomplete, not an error)

**Edit View**
- [ ] Edit modal layout — title left, value right on both mobile and desktop (matching view modal pattern)
- [ ] Image thumbnails in edit view — shrink uploaded screenshots to thumbnails so user doesn't scroll past them to reach editable fields
- [ ] Tap-to-zoom on thumbnails — integrate PhotoSwipe (https://photoswipe.com/) for pinch-zoom on mobile

**Pages**
- [ ] Homepage — landing page with visual overview of the system; explains the two-source approach and what the tool does
- [ ] Features / About page — bring back `/features` route; surface README-level explanation inside the app itself; upload guidance, screenshot type examples, calendar view explanation

---

### Phase 2 — Grievances
Generate grievance PDFs using stored punch data + user profile. Covers early punch, overtime, and daily total mismatches. Requires Phase 1.5 user profile and discrepancy proof flow to be complete first.

- [ ] Grievance form PDF — WeasyPrint
- [ ] Early punch grievance form
- [ ] Overtime split on grievance form

---

### Phase 3 — Production & Multi-user
Heroku deployment and multi-user support.

- [ ] Remove hardcoded Windows Tesseract path (cross-platform guard already in place via `platform.system()`)
- [ ] Add `tesseract-ocr` to `Aptfile` for `heroku-buildpack-apt`
- [ ] Migrate SQLite → Postgres (Heroku ephemeral filesystem makes SQLite unsuitable for production)
- [ ] Multi-user accounts — schema reserves space for `user_id` FK; no auth code yet
