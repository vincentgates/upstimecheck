import platform
import re
from datetime import datetime

import pytesseract
from PIL import Image, ImageEnhance

# On Windows, Tesseract isn't on PATH after install — point to it explicitly.
# On Linux (Heroku, etc.) it's installed via apt/buildpack and found on PATH automatically.
if platform.system() == 'Windows':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# ── UPS app / handheld terminal regexes ──────────────────────────────────────
# \s* handles "Punchedout" (no space) — common OCR drop on photo-of-screen
_PUNCH_RE       = re.compile(r'Punched\s*(In|Out)[^\d]{0,10}(\d{1,2}:\d{2})', re.IGNORECASE)
_SCHED_RE       = re.compile(r'Sched(?:uled)?[^\d]{0,15}(\d{1,2}:\d{2})', re.IGNORECASE)
_DAILY_TOTAL_RE = re.compile(r'(?:Daily\s+)?Total[^\d]{0,20}(\d+):(\d{2})', re.IGNORECASE)

# ── UPS official weekly time system (UPS.com Microsoft portal) ────────────────
# Format per day block:
#   Tue 06/16/2026
#   PAY ACTUAL  132.53
#   Start Time: 4.17   Pay Rate: 0.00
#   End Time:   9.48   Total Hours: 5.31
# Times are DECIMAL HOURS — 4.17 = 4h 10m (0.17 × 60).
# An asterisk on Start Time (e.g. "4.12*") means the worker punched in early.
_OFF_DATE_RE  = re.compile(r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{2}/\d{2}/\d{4})', re.IGNORECASE)
_OFF_PAY_RE   = re.compile(r'PAY\s+ACTUAL', re.IGNORECASE)
_OFF_START_RE = re.compile(r'Start\s+Time:\s*([\d.]+)(\*)?', re.IGNORECASE)
_OFF_END_RE   = re.compile(r'End\s+Time:\s*([\d.]+)', re.IGNORECASE)
_OFF_TOTAL_RE = re.compile(r'Total\s+Hours:\s*([\d.]+)', re.IGNORECASE)

_EXIF_DATE_TAGS = (36867, 36868, 306)  # DateTimeOriginal, DateTimeDigitized, DateTime
_TARGET_WIDTH = 1600  # downsample to this before OCR — Tesseract chokes on 8K images


def extract_punches(image_path, source, fallback_date=None):
    """
    OCR a screenshot and return a list of punch dicts ready for DB insert.

    source='app'      — UPS handheld terminal photo; date from EXIF or fallback_date.
    source='official' — UPS weekly web portal screenshot; dates parsed from on-screen
                        text (multiple days per image). fallback_date is ignored.

    Returns [] if nothing useful could be parsed.
    """
    img = _preprocess(image_path, source)
    raw_text = pytesseract.image_to_string(img, config='--psm 6')
    confidence = _page_confidence(img)

    if source == 'official':
        return _parse_official_weekly(raw_text, confidence)

    punch_date = _exif_date(image_path) or fallback_date
    if punch_date is None:
        return []
    return _parse(raw_text, punch_date, confidence)


def _exif_date(image_path):
    """Return the date the photo was taken from EXIF, or None if unavailable."""
    try:
        exif = Image.open(image_path)._getexif()
        if exif:
            for tag_id in _EXIF_DATE_TAGS:
                val = exif.get(tag_id)
                if val:
                    return datetime.strptime(val, '%Y:%m:%d %H:%M:%S').date()
    except Exception:
        pass
    return None


def _preprocess(image_path, source='app'):
    img = Image.open(image_path)
    w, h = img.size
    if source == 'app':
        # Trim phone bezel and empty space below the EXIT button so the card
        # content fills the frame — critical for 8K phone photos of the terminal
        img = img.crop((int(w * 0.03), int(h * 0.08), int(w * 0.97), int(h * 0.75)))
    # Downscale wide images — Tesseract chokes on 8K+ widths
    if img.width > _TARGET_WIDTH:
        scale = _TARGET_WIDTH / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    img = img.convert('L')
    return ImageEnhance.Contrast(img).enhance(1.5)


def _page_confidence(img):
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT,
                                     config='--psm 6')
    scores = [int(c) for c in data['conf'] if str(c) != '-1']
    return round(sum(scores) / len(scores) / 100, 3) if scores else 0.0


def _parse(raw_text, punch_date, confidence):
    """
    Parse raw OCR text from a UPS "Punch Out Summary" screen into punch dicts.

    Expected layout (official terminal):
        Punched In      03:54
        Punched Out     09:15
        Scheduled       03:45
        Daily Total     5:30
    Times are 24-hour with no AM/PM suffix.
    Date comes from EXIF, not from on-screen text.
    scheduled_time and daily_total_minutes may be None if not visible in the image.
    """
    scheduled_time = _parse_scheduled(raw_text)
    daily_total_minutes = _parse_daily_total(raw_text)

    punches = []
    for match in _PUNCH_RE.finditer(raw_text):
        direction, time_str = match.groups()
        punch_time = datetime.strptime(time_str, '%H:%M').time()
        punches.append({
            'date':                punch_date,
            'time':                punch_time,
            'type':                direction.lower(),
            'raw_ocr_text':        raw_text,
            'confidence':          confidence,
            'scheduled_time':      scheduled_time,
            'daily_total_minutes': daily_total_minutes,
        })
    return punches


def _parse_scheduled(raw_text):
    m = _SCHED_RE.search(raw_text)
    if m:
        return datetime.strptime(m.group(1), '%H:%M').time()
    return None


def _parse_daily_total(raw_text):
    m = _DAILY_TOTAL_RE.search(raw_text)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return None


# ── Official weekly portal parser ─────────────────────────────────────────────

def _decimal_hours_to_time(val_str):
    """Convert decimal-hours string (e.g. '4.17') to datetime.time.
    UPS portal stores times as decimal hours: 4.17 = 4h 10.2m → 04:10.
    """
    val = float(str(val_str).rstrip('*').strip())
    hours = int(val)
    minutes = round((val - hours) * 60)
    if minutes >= 60:
        hours += 1
        minutes -= 60
    return datetime.strptime(f'{hours:02d}:{minutes:02d}', '%H:%M').time()


def _parse_official_weekly(raw_text, confidence):
    """
    Parse the UPS official weekly time system (UPS.com Microsoft portal).

    One screenshot covers a full week. Each day block looks like:
        Tue 06/16/2026
        PAY ACTUAL  132.53
        Start Time: 4.17   Pay Rate: 0.00
        End Time:   9.48   Total Hours: 5.31

    Days with 'No Card' (no work) are skipped.
    An asterisk on Start Time (e.g. 4.12*) means the system detected an early punch —
    the worker arrived before the scheduled start. This is preserved in raw_ocr_text.
    Times are converted from decimal hours to HH:MM.
    Returns a flat list of punch dicts across all worked days found.
    """
    punches = []

    # Split text into per-day blocks on day-of-week + date lines
    blocks = re.split(
        r'(?=(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{2}/\d{2}/\d{4})',
        raw_text, flags=re.IGNORECASE
    )

    for block in blocks:
        date_m = _OFF_DATE_RE.search(block)
        if not date_m:
            continue
        if not _OFF_PAY_RE.search(block):
            continue  # No Card — day off, skip

        try:
            punch_date = datetime.strptime(date_m.group(1), '%m/%d/%Y').date()
        except ValueError:
            continue

        start_m = _OFF_START_RE.search(block)
        end_m   = _OFF_END_RE.search(block)
        total_m = _OFF_TOTAL_RE.search(block)

        if not start_m or not end_m:
            continue

        try:
            start_time = _decimal_hours_to_time(start_m.group(1))
            end_time   = _decimal_hours_to_time(end_m.group(1))
        except (ValueError, AttributeError):
            continue

        daily_total_minutes = None
        if total_m:
            try:
                daily_total_minutes = round(float(total_m.group(1)) * 60)
            except ValueError:
                pass

        common = {
            'raw_ocr_text':        block.strip(),
            'confidence':          confidence,
            'scheduled_time':      None,  # not shown on this screen
            'daily_total_minutes': daily_total_minutes,
        }
        punches.append({'date': punch_date, 'time': start_time, 'type': 'in',  **common})
        punches.append({'date': punch_date, 'time': end_time,   'type': 'out', **common})

    return punches
