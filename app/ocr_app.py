"""
app/ocr_app.py — UPS handheld terminal photo OCR pipeline
==========================================================

WHAT THIS FILE DOES
-------------------
Handles the 'app' upload source: a phone photo of the UPS handheld terminal
screen showing the "Punch Out Summary" card. Extracts punch_in, punch_out,
scheduled_time, and daily_total_minutes and returns a list of dicts ready
for insert into the app_punches table.

One image = one day = at most one record returned.

PREPROCESSING NOTES (important for tuning)
-------------------------------------------
The terminal screen displays time values inside teal/cyan colored boxes with
white text. Standard grayscale + contrast boost makes these boxes go dark and
the white text disappears — Tesseract sees nothing.

Fix: after grayscale + contrast boost, apply a binary threshold at 150.
Teal boxes become solid black, white text inside them stays white, and
Tesseract reads white-on-black cleanly with --psm 6.

Crop percentages (0.02, 0.10, 0.98, 0.68) were tuned against a real photo
(20260623_091726.jpg, 8000x6000px shot on Samsung Galaxy). If a new phone
or framing produces bad results, run ocr_debug.py and adjust these values.
The content card typically sits in the top ~68% of the frame; the bottom
third is empty screen below the EXIT button.

USED BY
-------
- ocr_debug.py (CLI testing harness)
- app/controllers/upload.py (Flask upload route, 'app' source branch)
"""

import platform
import re
from datetime import datetime

import pytesseract
from PIL import Image, ImageEnhance

# On Windows, Tesseract isn't on PATH after install — point to it explicitly.
# On Linux it's found on PATH automatically via apt/buildpack.
if platform.system() == 'Windows':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Regexes for the Punch Out Summary screen
# \s* handles "PunchedIn" (no space) — common OCR artifact on phone-of-screen photos
_PUNCH_RE       = re.compile(r'Punched\s*(In|Out)[^\d]{0,10}(\d{1,2}:\d{2})', re.IGNORECASE)
_SCHED_RE       = re.compile(r'Sch(?:ed(?:uled)?)?\s*Time[^\d]{0,15}(\d{1,2}:\d{2})', re.IGNORECASE)
_DAILY_TOTAL_RE = re.compile(r'Daily\s+Total[^\d]{0,20}(\d+):(\d{2})', re.IGNORECASE)

_EXIF_DATE_TAGS = (36867, 36868, 306)  # DateTimeOriginal, DateTimeDigitized, DateTime
_TARGET_WIDTH   = 1600  # downsample to this before OCR — Tesseract chokes on 8K images


def extract_punches(image_path, fallback_date=None):
    """
    OCR a terminal photo and return a list of punch dicts ready for DB insert.

    Date comes from EXIF metadata if available, otherwise fallback_date.
    Returns [] if no punches could be parsed (bad image, wrong crop, etc).
    Run ocr_debug.py to diagnose failures.
    """
    punch_date = _exif_date(image_path) or fallback_date
    if punch_date is None:
        return []

    img = _preprocess(image_path)
    raw_text = pytesseract.image_to_string(img, config='--psm 6')
    confidence = _page_confidence(img)

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


def _preprocess(image_path):
    img = Image.open(image_path)
    w, h = img.size
    img = img.crop((int(w * 0.02), int(h * 0.10), int(w * 0.98), int(h * 0.68)))
    if img.width > _TARGET_WIDTH:
        scale = _TARGET_WIDTH / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    img = img.convert('L')
    return ImageEnhance.Contrast(img).enhance(1.2)


def _page_confidence(img):
    """Tesseract page-level confidence score, 0.0–1.0."""
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT,
                                     config='--psm 6')
    scores = [int(c) for c in data['conf'] if str(c) != '-1']
    return round(sum(scores) / len(scores) / 100, 3) if scores else 0.0


def _parse(raw_text, punch_date, confidence):
    """
    Parse raw OCR text from a Punch Out Summary screen.

    Returns a list with at most one dict.
    punch_in / punch_out may be None if OCR missed one direction.
    scheduled_time and daily_total_minutes may be None if not visible.
    """
    scheduled_time      = _parse_scheduled(raw_text)
    daily_total_minutes = _parse_daily_total(raw_text)

    punch_in  = None
    punch_out = None
    for match in _PUNCH_RE.finditer(raw_text):
        direction, time_str = match.groups()
        t = datetime.strptime(time_str, '%H:%M').time()
        if direction.lower() == 'in':
            punch_in = t
        else:
            punch_out = t

    if punch_in is None and punch_out is None:
        return []

    return [{
        'date':                punch_date,
        'punch_in':            punch_in,
        'punch_out':           punch_out,
        'raw_ocr_text':        raw_text,
        'confidence':          confidence,
        'scheduled_time':      scheduled_time,
        'daily_total_minutes': daily_total_minutes,
    }]


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
