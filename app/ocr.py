import platform
import re
from datetime import datetime

import pytesseract
from PIL import Image, ImageEnhance

# On Windows, Tesseract isn't on PATH after install — point to it explicitly.
# On Linux (Heroku, etc.) it's installed via apt/buildpack and found on PATH automatically.
if platform.system() == 'Windows':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Allow up to 10 non-digit chars between label and time to absorb OCR noise
# e.g. "Punched Out), 09:15" — the "), " is junk the camera-photo OCR introduces
_PUNCH_RE = re.compile(r'Punched\s+(In|Out)[^\d]{0,10}(\d{1,2}:\d{2})', re.IGNORECASE)

_EXIF_DATE_TAGS = (36867, 36868, 306)  # DateTimeOriginal, DateTimeDigitized, DateTime
_TARGET_WIDTH = 1600  # downsample to this before OCR — Tesseract chokes on 8K images


def extract_punches(image_path, source):
    """
    OCR a screenshot and return a list of punch dicts ready for DB insert.

    Each dict contains: date, time, type, raw_ocr_text, confidence.
    Caller is responsible for adding source and creating Punch objects.
    Returns [] if EXIF date cannot be read — date from on-screen text is unreliable
    (the date corner is often cropped out of frame).
    """
    punch_date = _exif_date(image_path)
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
    # Trim phone bezel and empty space below the EXIT button so the card content
    # fills the frame — without this the teal time boxes are too small for Tesseract
    img = img.crop((int(w * 0.03), int(h * 0.08), int(w * 0.97), int(h * 0.75)))
    # Downscale to target width — upscaling an 8K image breaks Tesseract
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
        Punched In   03:54
        Punched Out  09:15
    Times are 24-hour with no AM/PM suffix.
    Date comes from EXIF, not from on-screen text.
    """
    punches = []
    for match in _PUNCH_RE.finditer(raw_text):
        direction, time_str = match.groups()
        punch_time = datetime.strptime(time_str, '%H:%M').time()
        punches.append({
            'date': punch_date,
            'time': punch_time,
            'type': direction.lower(),
            'raw_ocr_text': raw_text,
            'confidence': confidence,
        })
    return punches
