"""
ocr_debug.py — unified OCR debug harness for upstimecheck
===========================================================

PURPOSE
-------
This is the primary developer tool for testing and tuning the OCR pipelines.
It simulates exactly what the Flask upload route does — preprocessing,
Tesseract, parsing — and prints what would be saved to the database.

There are two pipelines, one per upload source:
  • 'app'      — photo of the UPS handheld terminal screen (app_punches table)
                 routes to app/ocr_app.py
  • 'official' — screenshot of the UPS weekly web portal (official_punches table)
                 routes to app/ocr_official.py

This script replaces the old one-off ocr_test_official.py, which is now deleted.
All official pipeline testing goes through here with the 'official' source arg.

USAGE
-----
  python ocr_debug.py <source> <image_path> [gold_standard_text]

  source         : 'app' or 'official'
  image_path     : path to the image file to OCR
  gold_standard  : (optional) known-correct text to compare against raw OCR output
                   e.g. text copied via Samsung Galaxy "copy text" feature.
                   When provided, a simple token match check is printed at the end.
                   Intentionally lightweight — not a full diff, just a quick sanity
                   flag so you know if Tesseract is in the ballpark.

EXAMPLES
--------
  python ocr_debug.py app uploads/test/20260612_091555.jpg
  python ocr_debug.py official uploads/test/20260620_193712_official.jpg
  python ocr_debug.py app uploads/test/20260623.jpg "Punched In 03:43 Punched Out 09:17"

OUTPUT
------
  1. EXIF date extracted from the image (app pipeline only)
  2. RAW OCR TEXT — exactly what lands in the raw_ocr_text DB column
  3. CONFIDENCE — Tesseract page-level confidence score (0.0–1.0)
  4. PARSED PUNCHES — structured fields that would be inserted into the DB
  5. GOLD STANDARD CHECK — (only if gold arg provided) loose token match result

TUNING NOTES FOR CLAUDE CODE
-----------------------------
  The preprocessing (crop, scale, grayscale, contrast) lives in:
    app/ocr_app.py      → _preprocess() for terminal photos
    app/ocr_official.py → _preprocess() for portal screenshots

  If raw OCR output looks garbled, start by tweaking _preprocess() in
  the relevant file. The crop percentages in ocr_app._preprocess() are
  the most likely culprit for bad app photo results — they were set
  conservatively and may not match all phone/orientation combos.

  The Tesseract config ('--psm 6') is set in extract_punches() in each
  ocr_*.py file. PSM modes worth trying for terminal photos: 4, 6, 11.
"""

import sys


def _usage():
    print("Usage: python ocr_debug.py <source> <image_path> [gold_standard_text]")
    print("  source: 'app' or 'official'")
    sys.exit(1)


def _gold_check(raw_text, gold):
    """
    Lightweight gold standard check.
    Strips whitespace from both strings and does a loose token scan —
    checks whether key tokens from the gold text appear in the raw OCR output.
    Not a line-by-line diff; just a quick sanity flag.
    """
    gold_tokens = gold.lower().split()
    raw_lower = raw_text.lower()
    matched = sum(1 for t in gold_tokens if t in raw_lower)
    pct = round(matched / len(gold_tokens) * 100) if gold_tokens else 0
    return matched, len(gold_tokens), pct


def main():
    if len(sys.argv) < 3:
        _usage()

    source = sys.argv[1].lower()
    image_path = sys.argv[2]
    gold = sys.argv[3] if len(sys.argv) > 3 else None

    if source not in ('app', 'official'):
        print(f"ERROR: source must be 'app' or 'official', got '{source}'")
        _usage()

    # Route to the correct pipeline
    if source == 'app':
        from app.ocr_app import extract_punches, _exif_date
        punch_date = _exif_date(image_path)
        print(f"\n=== EXIF DATE: {punch_date} ===")
        punches = extract_punches(image_path, fallback_date=punch_date)
    else:
        from app.ocr_official import extract_punches
        punches = extract_punches(image_path)

    # Raw OCR text and confidence come back on each punch record.
    # For display we pull from the first record, or re-run if no punches found.
    if punches:
        raw_text = punches[0].get('raw_ocr_text', '')
        confidence = punches[0].get('confidence', 0.0)
    else:
        # Nothing parsed — still show raw text so you can diagnose why
        if source == 'app':
            from app.ocr_app import _preprocess
        else:
            from app.ocr_official import _preprocess
        import pytesseract
        img = _preprocess(image_path)
        raw_text = pytesseract.image_to_string(img, config='--psm 6')
        confidence = 0.0

    print("\n=== RAW OCR TEXT (raw_ocr_text column) ===")
    print(raw_text)

    print(f"\n=== CONFIDENCE: {confidence} ===")

    print("\n=== PARSED PUNCHES (DB insert payload) ===")
    if punches:
        for p in punches:
            # Print every field except raw_ocr_text (already shown above)
            display = {k: v for k, v in p.items() if k != 'raw_ocr_text'}
            for k, v in display.items():
                print(f"  {k}: {v}")
            print()
    else:
        print("  (no punches parsed — check raw OCR text above)")

    if gold:
        matched, total, pct = _gold_check(raw_text, gold)
        print(f"\n=== GOLD STANDARD CHECK ===")
        print(f"  Tokens matched: {matched}/{total} ({pct}%)")
        if pct >= 80:
            print("  OK looks good")
        elif pct >= 50:
            print("  ~ Partial match — some fields may be off")
        else:
            print("  X Low match — preprocessing likely needs tuning")


if __name__ == '__main__':
    main()
