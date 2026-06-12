"""
Quick diagnostic: run pytesseract on a test image and print raw output.
Usage:  python ocr_debug.py uploads/test/20260612_091555.jpg
"""
import sys
from app.ocr import _preprocess, _parse, _exif_date
import pytesseract


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'uploads/test/20260612_091555.jpg'

    punch_date = _exif_date(path)
    print(f'=== EXIF DATE: {punch_date} ===')

    img = _preprocess(path)
    raw = pytesseract.image_to_string(img, config='--psm 6')

    print('=== RAW OCR TEXT ===')
    print(raw)
    print('=== PARSED PUNCHES ===')
    for p in _parse(raw, punch_date, 0.0):
        print(p)


if __name__ == '__main__':
    main()
