import os
import tempfile
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.db import db, Punch
from app.ocr import extract_punches

upload_bp = Blueprint('upload', __name__)

_ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg'}


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

        try:
            punches = extract_punches(tmp_path, source)
        except Exception as e:
            flash(f'OCR error: {e}', 'danger')
            return redirect(url_for('upload.upload'))
        finally:
            os.unlink(tmp_path)

        if not punches:
            flash(
                'Screenshot processed but no punches were found. '
                'The parser needs tuning — share the screenshot so the regex can be written.',
                'warning'
            )
            return redirect(url_for('upload.upload'))

        for data in punches:
            db.session.add(Punch(source=source, **data))
        db.session.commit()

        flash(f'Saved {len(punches)} punch(es) from {source} screenshot.', 'success')
        return redirect(url_for('calendar.show_calendar'))

    return render_template('upload/upload.html')
