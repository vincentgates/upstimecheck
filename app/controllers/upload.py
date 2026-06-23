import os
import tempfile
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory
from PIL import Image

from app.db import db, AppPunch, OfficialPunch
from app.ocr_app import extract_punches as _extract_app, _exif_date
from app.ocr_official import extract_punches as _extract_official

upload_bp = Blueprint('upload', __name__)

_ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg'}
_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'uploads', 'processed')
_DISPLAY_WIDTH = 1600

_SOURCE_MODEL = {'app': AppPunch, 'official': OfficialPunch}


@upload_bp.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        source = request.form.get('source')
        file = request.files.get('screenshot')

        if not file or not file.filename:
            flash('No file selected.', 'danger')
            return redirect(url_for('upload.upload'))

        if source not in _SOURCE_MODEL:
            flash('Please select a source (UPS App or Official System).', 'danger')
            return redirect(url_for('upload.upload'))

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in _ALLOWED_EXTENSIONS:
            flash('Only PNG and JPG screenshots are supported.', 'danger')
            return redirect(url_for('upload.upload'))

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        exif_date = _exif_date(tmp_path)

        fallback_date = exif_date
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
            if source == 'app':
                punches = _extract_app(saved_path, fallback_date=fallback_date)
            else:
                punches = _extract_official(saved_path)
        except Exception as e:
            flash(f'OCR error: {e}', 'danger')
            return redirect(url_for('upload.upload'))
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        if not punches:
            flash(
                'No punches found. If this image has no photo metadata (e.g. a screenshot), '
                'enter the punch date manually and try again.',
                'warning'
            )
            return redirect(url_for('upload.upload'))

        Model = _SOURCE_MODEL[source]

        # Replace existing records for every date found in this upload.
        dates_found = list({p['date'] for p in punches})
        stale = Model.query.filter(Model.date.in_(dates_found)).all()
        if stale:
            orphaned_images = {p.image_path for p in stale if p.image_path}
            for p in stale:
                db.session.delete(p)
            db.session.commit()
            for img_file in orphaned_images:
                if not _image_still_referenced(img_file):
                    full = os.path.join(_UPLOAD_DIR, img_file)
                    if os.path.exists(full):
                        os.remove(full)

        for data in punches:
            db.session.add(Model(image_path=image_filename, **data))
        db.session.commit()

        first_date = min(dates_found)
        source_label = 'UPS App' if source == 'app' else 'Official System'
        flash(
            f'Saved {len(punches)} day(s) from {source_label} screenshot.',
            'success'
        )
        return redirect(url_for('calendar.show_calendar',
                                date=first_date.strftime('%Y-%m-%d')))

    return render_template('upload/upload.html')


@upload_bp.route('/uploads/processed/<filename>')
def serve_upload(filename):
    """Serve saved punch screenshots outside of static/ for future access control."""
    return send_from_directory(os.path.abspath(_UPLOAD_DIR), filename)


def _image_still_referenced(image_path):
    """Return True if any record in either table still points to this image."""
    return (
        AppPunch.query.filter_by(image_path=image_path).count() > 0
        or OfficialPunch.query.filter_by(image_path=image_path).count() > 0
    )


def _save_display_copy(tmp_path, source, ext):
    """Downsample to display width, save color copy, return filename."""
    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    img = Image.open(tmp_path)
    if img.width > _DISPLAY_WIDTH:
        scale = _DISPLAY_WIDTH / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{source}{ext}"
    img.save(os.path.join(_UPLOAD_DIR, filename), quality=85)
    return filename
