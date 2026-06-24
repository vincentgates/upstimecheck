import platform
import re
from datetime import datetime

import pytesseract
from PIL import Image, ImageEnhance

if platform.system() == 'Windows':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# ── UPS official weekly time system (UPS.com Microsoft portal) ────────────────
# Format per day block (worked day):
#   Tue 06/16/2026
#   Pay Code: Gross Pay:
#   PAY ACTUAL  132.53
#   Start Time: 4.17   Pay Rate: 0.00
#   End Time:   9.48   Total Hours: 5.31
#
# Times are DECIMAL HOURS — 4.17 = 4h 10m (0.17 × 60).
# An asterisk on Start Time (e.g. "4.12*") is stored as corrected=True.
_OFF_DATE_RE     = re.compile(r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{2}/\d{2}/\d{4})', re.IGNORECASE)
# Inline: "Pay Code: TEMP STS CHANGE - PAY ACTUAL Gross Pay: 132.53" (TCD-style)
_OFF_PAY_INLINE_RE  = re.compile(r'Pay\s+Code:\s*(.+?)\s+Gross\s+Pay:\s*([\d.]+)', re.IGNORECASE)
# Two-line: "Pay Code: Gross Pay:\nPAY ACTUAL  132.53" (normal days)
_OFF_PAY_TWOLINE_RE = re.compile(r'Pay\s+Code:\s*Gross\s+Pay:\s*\n\s*(\S.+?)\s+([\d.]+)\s*$', re.IGNORECASE | re.MULTILINE)
_OFF_START_RE    = re.compile(r'Start\s+Time:\s*([\d.N/A]+)(\*)?', re.IGNORECASE)
_OFF_END_RE      = re.compile(r'End\s+Time:\s*([\d.N/A]+)', re.IGNORECASE)
_OFF_RATE_RE     = re.compile(r'Pay\s+Rate:\s*([\d.]+)', re.IGNORECASE)
_OFF_TOTAL_RE    = re.compile(r'Total\s+Hours:\s*([\d.]+)', re.IGNORECASE)

_TARGET_WIDTH = 1600


def extract_punches(image_path):
    img = _preprocess(image_path)
    raw_text = pytesseract.image_to_string(img, config='--psm 6')
    confidence = _page_confidence(img)
    return _parse_official_weekly(raw_text, confidence)


def _preprocess(image_path):
    img = Image.open(image_path)
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
    records = []

    blocks = re.split(
        r'(?=(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{2}/\d{2}/\d{4})',
        raw_text, flags=re.IGNORECASE
    )

    for block in blocks:
        date_m = _OFF_DATE_RE.search(block)
        if not date_m:
            continue

        try:
            punch_date = datetime.strptime(date_m.group(1), '%m/%d/%Y').date()
        except ValueError:
            continue

        pay_m = _OFF_PAY_INLINE_RE.search(block)
        if pay_m and pay_m.group(1).strip():
            pay_code  = re.sub(r'\s+', ' ', pay_m.group(1).strip())
            gross_pay = _safe_float(pay_m.group(2))
        else:
            pay_m = _OFF_PAY_TWOLINE_RE.search(block)
            if not pay_m:
                continue
            pay_code  = re.sub(r'\s+', ' ', pay_m.group(1).strip())
            gross_pay = _safe_float(pay_m.group(2))

        rate_m   = _OFF_RATE_RE.search(block)
        pay_rate = _safe_float(rate_m.group(1)) if rate_m else None

        total_m = _OFF_TOTAL_RE.search(block)
        daily_total_minutes = None
        if total_m:
            v = _safe_float(total_m.group(1))
            daily_total_minutes = round(v * 60) if v is not None else None

        if pay_code.upper() == 'NO CARD':
            records.append({
                'date':                punch_date,
                'pay_code':            'No Card',
                'gross_pay':           gross_pay,
                'punch_in':            None,
                'punch_out':           None,
                'pay_rate':            pay_rate,
                'daily_total_minutes': daily_total_minutes if daily_total_minutes is not None else 0,
                'corrected':           False,
                'raw_ocr_text':        block.strip(),
                'confidence':          confidence,
            })
            continue

        start_m = _OFF_START_RE.search(block)
        end_m   = _OFF_END_RE.search(block)

        if not start_m or not end_m:
            continue

        corrected = bool(start_m.group(2))
        start_val = start_m.group(1).strip()
        end_val   = end_m.group(1).strip()

        if start_val in ('N/A', 'N', 'A') or end_val in ('N/A', 'N', 'A'):
            continue  # PAY ACTUAL row but times are N/A — skip

        try:
            punch_in  = _decimal_hours_to_time(start_val)
            punch_out = _decimal_hours_to_time(end_val)
        except (ValueError, AttributeError):
            continue

        records.append({
            'date':                punch_date,
            'pay_code':            pay_code,
            'gross_pay':           gross_pay,
            'punch_in':            punch_in,
            'punch_out':           punch_out,
            'pay_rate':            pay_rate,
            'daily_total_minutes': daily_total_minutes,
            'corrected':           corrected,
            'raw_ocr_text':        block.strip(),
            'confidence':          confidence,
        })

    return records


def _safe_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
