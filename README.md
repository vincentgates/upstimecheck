# UPS Time Reconciliation Tool

Personal tool for cross-checking UPS app clock-in/out times against the official UPS time system. Upload screenshots from both systems, OCR extracts the punch data, and the app shows a weekly view highlighting mismatches.

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
│   ├── ocr_app.py            # OCR pipeline — UPS terminal phone photos
│   ├── ocr_official.py       # OCR pipeline — UPS web portal screenshots
│   ├── controllers/
│   │   ├── pages.py          # Static routes
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

There are two separate OCR pipelines, one per upload source:

### app/ocr_app.py — terminal photo pipeline
Handles phone photos of the UPS handheld terminal "Punch Out Summary" screen.
One image → one day → one DB record.

**Preprocessing (tuned 2026-06-23 against Samsung Galaxy 8000×6000px photos):**
- Crop: 2% left, 10% top, 98% right, 68% bottom — removes bezel and EXIT button
- Downscale to 1600px wide
- Grayscale + 1.2× contrast boost (intentionally conservative — no threshold)

The time values appear in teal boxes with white text. Heavy preprocessing destroys
them. The 1.2× contrast is the correct setting — do not increase it.

### app/ocr_official.py — web portal screenshot pipeline
Handles screenshots of the UPS weekly time portal (Microsoft/UPS.com).
One image → one week → multiple DB records (one per worked day).

Times are stored as decimal hours in the portal: `4.17 = 4h 10m`.
`_decimal_hours_to_time()` handles conversion.

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

**Output:**
1. EXIF date (app only)
2. Raw OCR text — exactly what lands in `raw_ocr_text` DB column
3. Confidence score (0.0–1.0)
4. Parsed punch dict — what would be inserted into the DB
5. Gold standard check — token match % (optional, 80%+ is good)

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
| `pay_code` | VARCHAR | `PAY ACTUAL` or `No Card` |
| `gross_pay` | FLOAT | |
| `pay_rate` | FLOAT | |
| `daily_total_minutes` | INTEGER | |
| `corrected` | BOOLEAN | True if start time had asterisk (*) |
| `raw_ocr_text` | TEXT | |
| `confidence` | FLOAT | |
| `created_at` | DATETIME | |

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
- The UPS app screenshot IS the proof for an early punch grievance

---

## Current state (Phase 1)

- [x] Flask app boots, routes work
- [x] OCR pipeline refactored — separate `ocr_app.py` and `ocr_official.py`
- [x] `ocr_debug.py` unified debug harness for both pipelines
- [x] Preprocessing tuned — terminal photos OCR correctly at 0.80+ confidence
- [x] EXIF date extraction
- [x] Scheduled time + daily total OCR-scraped and stored
- [x] Weekly calendar — live DB data, accordion + View modals, confidence %
- [x] Edit modal — original image left, editable fields right
- [x] Cross-check logic — flags punch time and daily total mismatches
- [x] Early punch detection
- [ ] Grievance form PDF — WeasyPrint (planned)
- [ ] Early punch grievance form
- [ ] Overtime split on grievance form

## Phase 2 (future)
Multi-user accounts. Schema reserves space for `user_id` FK. No auth code yet.
