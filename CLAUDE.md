# Project: UPS Time Reconciliation Tool

## Deployment target — READ THIS FIRST

**Production runs on Linux (Heroku or similar PaaS). Development runs on Windows.**
This is a hard constraint that applies to every code change, forever.

Rules that follow from this:
- **Never hardcode Windows paths.** No `C:\...`, no `r'C:\Program Files\...'` anywhere in
  application code. Use `platform.system()` guards or environment variables instead.
- **No Windows-only binaries.** Any system dependency (e.g. Tesseract) must be installable
  on Linux via `apt` / a Heroku buildpack. Document it in `Aptfile` or `Procfile` notes.
- **Tesseract path** is set conditionally in `app/ocr_app.py` and `app/ocr_official.py` —
  Windows gets the hardcoded installer path; Linux finds it on `PATH` automatically.
- **Secret key, DB URL, and any credentials** must come from environment variables before
  any production push. The current hardcoded key in `app/__init__.py` is dev-only.
- **SQLite is fine for now.** Heroku's ephemeral filesystem means the DB resets on dyno
  restart — acceptable for Phase 1 testing. Phase 2 will need a persistent store
  (PostgreSQL via `heroku-postgres` add-on, or an attached volume).

When adding any new system-level dependency, ask: *does this work on a fresh Ubuntu dyno?*

---

## Status
Phase 1 in progress. OCR pipeline refactored and tuned. Calendar reads DB. Cross-check
logic live. Scheduled time + daily total tracking in place. Grievance form PDF is next.

---

## 🆕 Session handoff — 2026-06-24

### What was completed this session

**Focus: `app/ocr_official.py` and `ocr_debug.py` — DONE and verified.**

**Problem solved — TCD day (Mon 06/22) was silently skipped:**
The old `_OFF_PAY_CODE_RE` only matched literal `PAY ACTUAL` or `No Card`. Monday had pay
code `TEMP STS CHANGE - PAY ACTUAL` which didn't match, dropping the entire block.

**Problem solved — pay code was hardcoded on insert:**
`pay_code` was always written as `'PAY ACTUAL'` regardless of what the portal said.

**Fix — two-format regex approach (applied and tested):**
The UPS portal uses two different block layouts depending on pay code type:

- **Normal days** (two-line): `Pay Code: Gross Pay:\nPAY ACTUAL  132.53`
- **TCD/special days** (each field on its own line):
  ```
  Pay Code:
  TEMP STS CHANGE - PAY ACTUAL
  Gross Pay:
  417.94
  ```

The fix uses two regexes and tries them in order:
```python
# Inline/multi-line: pay code text sits between Pay Code: and Gross Pay: labels
_OFF_PAY_INLINE_RE  = re.compile(r'Pay\s+Code:\s*(.+?)\s+Gross\s+Pay:\s*([\d.]+)', re.IGNORECASE)
# Standard two-line: "Pay Code: Gross Pay:\nPAY ACTUAL  132.53"
_OFF_PAY_TWOLINE_RE = re.compile(r'Pay\s+Code:\s*Gross\s+Pay:\s*\n\s*(\S.+?)\s+([\d.]+)\s*$', re.IGNORECASE | re.MULTILINE)
```

Key insight: `_OFF_PAY_INLINE_RE` has no DOTALL but `\s` still matches newlines, so it
correctly handles TCD blocks where each field is on its own line. The two-line format
fails the inline regex (no captured text between labels) and falls through to `_OFF_PAY_TWOLINE_RE`.

**`ocr_debug.py` — fixed to show all blocks:**
Now prints RAW OCR BLOCK + PARSED FIELDS for every record, not just `punches[0]`.

**Verified against test image — all 7 days parsed correctly:**
```
Sun 06/21  No Card           —         —        0 min
Mon 06/22  TEMP STS CHANGE - PAY ACTUAL  08:55  19:16  590 min  ← was missing before
Tue 06/23  PAY ACTUAL        04:10     09:17    307 min
Wed 06/24  PAY ACTUAL        04:00     09:31    331 min
Thu 06/25  No Card           —         —        0 min
Fri 06/26  No Card           —         —        0 min
Sat 06/27  No Card           —         —        0 min
```
Confidence: 0.947

### What to do next

1. Commit `app/ocr_official.py` and `ocr_debug.py`
2. **Next feature: grievance form PDF generation** (see End Goal section below)

---

## OCR Architecture — READ BEFORE TOUCHING OCR FILES

The OCR pipeline was refactored on 2026-06-23 into two separate modules. The old
monolithic `app/ocr.py` is deprecated and should be deleted once confirmed clean.

### Two pipelines, two files

| File | Source | Upload type |
|---|---|---|
| `app/ocr_app.py` | `source='app'` | Phone photo of UPS handheld terminal screen |
| `app/ocr_official.py` | `source='official'` | Screenshot of UPS weekly web portal |

`app/controllers/upload.py` routes to the correct pipeline based on `source`.
Never add logic to the old `app/ocr.py` — it is dead code.

### app/ocr_app.py — terminal photo pipeline

Handles the "Punch Out Summary" card shown on the UPS handheld terminal after punching out.
One image = one day = at most one DB record.

**Preprocessing (tuned 2026-06-23):**
- Crop: left 2%, top 10%, right 98%, bottom 68% — removes phone bezel and EXIT button area
- Downscale to 1600px wide — Tesseract chokes on 8K Samsung Galaxy photos
- Grayscale + light contrast boost (1.2×) — NO binary threshold
- The threshold was removed because it destroyed label text. Light contrast only is correct.
- Tuned against real photo: `20260623_091726.jpg` (8000×6000px, Samsung Galaxy)

**Key constraint:** Time values appear inside teal/cyan boxes with white text. Too much
contrast or any threshold makes these boxes go solid black and Tesseract loses the values.
The 1.2× contrast is intentionally conservative — this is correct, do not "improve" it.

**Regexes:**
- `_PUNCH_RE` — matches "Punched In/Out" + time
- `_SCHED_RE` — matches "Sch Time" / "Scheduled Time" + time
- `_DAILY_TOTAL_RE` — matches "Daily Total" + HH:MM

Note: OCR of a phone-of-screen photo often clips the left edge of labels
("Punch Out Summary" → "ut Summary", "Sch Time" → "ch Time"). Regexes use
loose prefixes to tolerate this. Do not tighten them without testing against
real images via `ocr_debug.py`.

### app/ocr_official.py — web portal screenshot pipeline

Handles the UPS official weekly time system (Microsoft portal on UPS.com).
One image = one week = multiple DB records (one per worked day).

**Key quirk:** Portal stores times as decimal hours, not HH:MM.
`4.17 = 4h 10m` (0.17 × 60 = 10.2 minutes). `_decimal_hours_to_time()` converts these.

**Pay codes:**
Pay codes are captured as-is from the portal — whatever text appears between `Pay Code:`
and `Gross Pay:` in a day block. Known examples include:
- `PAY ACTUAL` — normal worked day with start/end times
- `TEMP STS CHANGE - PAY ACTUAL` — TCD (Temporary Cover Driver) day
- `No Card` — day where system has no punch record (grievable)

Do NOT hardcode pay codes into the regex. The current approach captures any pay code
automatically. If a new pay code causes a parse failure, check the raw OCR block first.

---

## Debug harness — ocr_debug.py

`ocr_debug.py` in the project root is the primary tool for testing and tuning OCR.
It routes to the correct pipeline and prints exactly what would be saved to the DB.

```
python ocr_debug.py app path/to/image.jpg
python ocr_debug.py official path/to/image.jpg
python ocr_debug.py app path/to/image.jpg "gold standard text for comparison"
```

**Output per punch record:**
1. RAW OCR BLOCK — the raw text for that day block
2. PARSED FIELDS — the dict that would be inserted into the DB
3. CONFIDENCE score (page-level, same across all records)
4. GOLD STANDARD CHECK — token match % (only if 3rd arg provided)

The gold standard arg is optional. Pass Samsung Galaxy "copy text" output as the
3rd argument to get a quick quality score. 80%+ = good. Below 50% = needs tuning.

When OCR output is bad, the first thing to check is the preprocessed image:
```
python -c "from app.ocr_app import _preprocess; _preprocess('path/to/img.jpg').save('debug_preprocessed.png')"
```
Upload `debug_preprocessed.png` and visually inspect before changing any code.

---

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

---

## UPS Business Logic — READ BEFORE WRITING CALCULATION CODE

### Work week and schedule
- The operational week is **Sunday through Saturday**.
- **Sunday is typically a no-service day** — the natural upload day for the prior Mon–Sat week.
- **Saturday evening shifts** can run past midnight into early Sunday. The punch date
  for those records is **Saturday** — determined by EXIF timestamp, never by clock hour.

### Part-time overtime threshold
> Part-time employees earn **1.5× pay for every minute worked beyond 5 hours (300 minutes)
> in a single workday.**

This is a **daily** threshold, not weekly.

```
regular_minutes  = min(actual_worked_minutes, 300)
overtime_minutes = max(actual_worked_minutes - 300, 0)
```

### Scheduled time is mandatory
- `scheduled_time` must be present for any meaningful pay or overtime calculation.
- Never calculate overtime without a known `scheduled_time`. Show a UI warning if missing.

### Early punch rules
**State A — no proof (default):** `effective_start = scheduled_time`. Early minutes don't count.
**State B — proof present:** `effective_start = punch_in`. Early minutes are grievable.

---

## Upload workflow
- `source='app'` → UPS handheld terminal clock-in screenshots
- `source='official'` → UPS weekly web portal screenshot
- Upload Sunday after the full Mon–Sat week is complete.

---

## Stack
- Python / Flask 3.x
- SQLite (`database.db`) via Flask-SQLAlchemy
- OCR: pytesseract + Tesseract binary
- PDF (planned): WeasyPrint
- Frontend: Bootstrap 5, Jinja2, SASS via npm

---

## Phases
**Phase 1 (current):** Single-user, no auth. Goal: OCR → DB → weekly view → cross-check.
**Phase 2 (later):** Multi-user accounts, encrypted credentials, user-scoped uploads.

Do not add auth or user tables until Phase 1 is stable.

---

## Branching
Git-flow style. Work on `develop`, feature branches off `develop`, releases cut into `main`.

---

## Data model
Defined in `app/db.py`.

```
app_punches:      id, date, punch_in, punch_out, scheduled_time,
                  daily_total_minutes, raw_ocr_text, confidence,
                  image_path, created_at

official_punches: id, date, punch_in, punch_out, pay_code, gross_pay,
                  pay_rate, daily_total_minutes, corrected,
                  raw_ocr_text, confidence, created_at
```

---

## Conventions

**DB access:** All queries go through `app/db.py`. No raw SQL in controllers.
**Models:** Flask-SQLAlchemy ORM. Add new models to `app/db.py`.
**Blueprints:** One per feature area under `app/controllers/`. Register in `app/__init__.py`.
**Schema changes:** Use `db.create_all()` for Phase 1. Switch to Flask-Migrate when stable.
**No dead imports:** Don't leave unused blueprints or packages wired in.
**Setup:** Delete `.venv` and rerun `setup_env.bat` for a clean environment rebuild.
**Secret key:** Currently hardcoded — move to env var before any networked deployment.

---

## .gitignore reminders
These should never be committed:
- `database.db` — runtime file, resets on Heroku anyway
- `debug_preprocessed.png` — temp debug artifact from ocr_debug.py
- `output.zip` — git archive artifact
- `.venv/` — local Python environment
