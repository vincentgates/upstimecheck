from datetime import date, time

import pytesseract
from PIL import Image, ImageEnhance


def extract_punches(image_path, source):
    """
    OCR a screenshot and return a list of punch dicts ready for DB insert.

    Each dict contains: date, time, type, raw_ocr_text, confidence.
    Caller is responsible for adding source and creating Punch objects.
    """
    img = _preprocess(image_path)
    raw_text = pytesseract.image_to_string(img)
    confidence = _page_confidence(img)
    return _parse(raw_text, source, confidence)


def _preprocess(image_path):
    img = Image.open(image_path).convert('L')  # grayscale cuts color noise
    return ImageEnhance.Contrast(img).enhance(2.0)


def _page_confidence(img):
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    scores = [int(c) for c in data['conf'] if str(c) != '-1']
    return round(sum(scores) / len(scores) / 100, 3) if scores else 0.0


def _parse(raw_text, source, confidence):
    """
    Parse raw OCR text into punch dicts.

    TODO: implement once real UPS screenshots are available.

    What to look for (expected, not yet confirmed):
      UPS app screenshots likely show date headers followed by In/Out time pairs,
      e.g. "Mon 06/09" then "In  04:27 AM" / "Out  09:00 AM".
      Official system screenshots may differ in layout — check both side by side.

    Each returned dict must have:
      date (datetime.date), time (datetime.time), type ('in' or 'out'),
      raw_ocr_text (str), confidence (float 0-1).

    Example skeleton to fill in:
      DATE_RE  = re.compile(r'...')
      TIME_RE  = re.compile(r'(\d{1,2}:\d{2}\s*[AP]M)', re.IGNORECASE)
      ...

    Return [] for now so the upload route can report "no punches found"
    rather than crashing.
    """
    punches = []
    return punches
