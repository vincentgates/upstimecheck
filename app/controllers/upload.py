import os
import tempfile
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory
from PIL import Image

from app.db import db, Punch
from app.ocr import extract_punches

upload_bp = Blueprint('upload', __name__)

_ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg'}
_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'uploads', 'processed')
_DISPLAY_WIDTH = 1600  # max width for saved display copy


@upload_bp.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        source = request.form.get('source')
        file = request.files.get('screenshot')

        if not file or not file.filename:
            flash('No file selected.', 'danger')
            return redirect(url_for('upload.upload'))

        if source not in ('app', 'official'):
            flash('Please select a source (UPS App or Official System).', 'danger')
            return redirect(url_for('upload.upload'))

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in _ALLOWED_EXTENSIONS:
            flash('Only PNG and JPG screenshots are supported.', 'danger')
            return redirect(url_for('upload.upload'))

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        fallback_date = None
        date_str = request.form.get('punch_date', '').strip()
        if date_str:
            try:
                fallback_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format.', 'danger')
                return redirect(url_for('upload.upload'))

        try:
            image_filename = _save_display_copy(tmp_path, source, ext)
            saved_path = os.path.join(_UPLOAD_DIR, image_filename)
            punches = extract_punches(saved_path, source, fallback_date=fallback_date)
        except Exception as e:
            flash(f'OCR error: {e}', 'danger')
            return redirect(url_for('upload.upload'))
        finally:
            os.unlink(tmp_path)

        if not punches:
            flash(
                'No punches found. If this image has no photo metadata (e.g. a screenshot), '
                'enter the punch date manually and try again.',
                'warning'
            )
            return redirect(url_for('upload.upload'))

        for data in punches:
            db.session.add(Punch(source=source, image_path=image_filename, **data))
        db.session.commit()

        flash(f'Saved {len(punches)} punch(es) from {source} screenshot.', 'success')
        return redirect(url_for('calendar.show_calendar'))

    return render_template('upload/upload.html')


@upload_bp.route('/uploads/processed/<filename>')
def serve_upload(filename):
    """Serve saved punch screenshots outside of static/ for future access control."""
    return send_from_directory(os.path.abspath(_UPLOAD_DIR), filename)


def _save_display_copy(tmp_path, source, ext):
    """Downsample to display width, save color copy, return filename."""
    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    img = Image.open(tmp_path)
    if img.width > _DISPLAY_WIDTH:
        scale = _DISPLAY_WIDTH / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    # Convert RGBA/P modes to RGB so JPEG save always works
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{source}{ext}"
    img.save(os.path.join(_UPLOAD_DIR, filename), quality=85)
    return filename
