import os
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.db import db, AppPunch, OfficialPunch
from .models import get_week_days, check_discrepancies, get_daily_summaries

_UPLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'uploads', 'processed')
)

_SOURCE_MODEL = {'app': AppPunch, 'official': OfficialPunch}

calendar_bp = Blueprint('calendar', __name__)


@calendar_bp.route('/cal')
@calendar_bp.route('/cal/<date>')
def show_calendar(date=None):
    today = datetime.today().date()
    if date:
        try:
            given = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            given = today
    else:
        given = today

    # Resolve to the Saturday that ends the week containing `given`
    week_end = given + timedelta((5 - given.weekday()) % 7)
    week_start = week_end - timedelta(days=6)
    days = get_week_days(week_start, week_end)

    app_punches = (
        AppPunch.query
        .filter(AppPunch.date >= week_start, AppPunch.date <= week_end)
        .order_by(AppPunch.date)
        .all()
    )
    official_punches = (
        OfficialPunch.query
        .filter(OfficialPunch.date >= week_start, OfficialPunch.date <= week_end)
        .order_by(OfficialPunch.date)
        .all()
    )

    app_by_date      = {p.date: p for p in app_punches}
    official_by_date = {p.date: p for p in official_punches}

    discrepancies   = check_discrepancies(app_by_date, official_by_date)
    daily_summaries = get_daily_summaries(app_by_date, official_by_date)

    return render_template(
        'calendar/cal-weekly.html',
        days=days,
        app_by_date=app_by_date,
        official_by_date=official_by_date,
        discrepancies=discrepancies,
        daily_summaries=daily_summaries,
        week_start=week_start,
        week_end=week_end,
        formatted_week_end=week_end.strftime('%m/%d/%Y'),
        prev_week=(week_end - timedelta(days=7)).strftime('%Y-%m-%d'),
        next_week=(week_end + timedelta(days=7)).strftime('%Y-%m-%d'),
    )


@calendar_bp.route('/cal/<date>/edit', methods=['POST'])
def edit_punches(date):
    """Update both AppPunch and OfficialPunch for the given date from one form submission."""
    try:
        target_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date.', 'danger')
        return redirect(url_for('calendar.show_calendar'))

    ap = AppPunch.query.filter_by(date=target_date).first()
    op = OfficialPunch.query.filter_by(date=target_date).first()

    try:
        if ap:
            ap.scheduled_time      = _parse_time(request.form.get('scheduled_time', ''))
            ap.punch_in            = _parse_time(request.form.get('app_punch_in',   ''))
            ap.punch_out           = _parse_time(request.form.get('app_punch_out',  ''))
            ap.daily_total_minutes = _parse_total(request.form.get('app_daily_total', ''))
        if op:
            op.punch_in            = _parse_time(request.form.get('off_punch_in',   ''))
            op.punch_out           = _parse_time(request.form.get('off_punch_out',  ''))
            op.daily_total_minutes = _parse_total(request.form.get('off_daily_total', ''))
            op.corrected           = request.form.get('off_corrected') == 'on'
            pay_code = request.form.get('off_pay_code', '').strip()
            if pay_code:
                op.pay_code = pay_code
            gross = request.form.get('off_gross_pay', '').strip()
            op.gross_pay = float(gross) if gross else None
            rate = request.form.get('off_pay_rate', '').strip()
            op.pay_rate = float(rate) if rate else None
    except ValueError as e:
        flash(f'Invalid value: {e}', 'warning')
        return redirect(url_for('calendar.show_calendar', date=date))

    db.session.commit()
    flash('Punches updated.', 'success')
    return redirect(url_for('calendar.show_calendar', date=date))


@calendar_bp.route('/cal/<date>/delete', methods=['POST'])
def delete_day(date):
    """Delete all records for a date from both tables."""
    try:
        target_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date.', 'danger')
        return redirect(url_for('calendar.show_calendar'))

    images_to_check = set()
    for Model in (AppPunch, OfficialPunch):
        records = Model.query.filter_by(date=target_date).all()
        for r in records:
            if r.image_path:
                images_to_check.add(r.image_path)
            db.session.delete(r)
    db.session.commit()

    for img in images_to_check:
        if not _image_still_referenced(img):
            full = os.path.join(_UPLOAD_DIR, img)
            if os.path.exists(full):
                os.remove(full)

    flash(f'All records for {target_date.strftime("%b %d")} deleted.', 'success')
    return redirect(url_for('calendar.show_calendar', date=date))


@calendar_bp.route('/cal/<date>/delete/<source>', methods=['POST'])
def delete_punch(date, source):
    """Delete a single source's record for a date (used from Edit modal)."""
    Model = _SOURCE_MODEL.get(source)
    if not Model:
        flash('Invalid source.', 'danger')
        return redirect(url_for('calendar.show_calendar'))

    try:
        target_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date.', 'danger')
        return redirect(url_for('calendar.show_calendar'))

    p = Model.query.filter_by(date=target_date).first()
    if p:
        image_path = p.image_path
        db.session.delete(p)
        db.session.commit()
        if image_path and not _image_still_referenced(image_path):
            full = os.path.join(_UPLOAD_DIR, image_path)
            if os.path.exists(full):
                os.remove(full)

    source_label = 'UPS App' if source == 'app' else 'Official System'
    flash(f'{source_label} record for {target_date.strftime("%b %d")} deleted.', 'success')
    return redirect(url_for('calendar.show_calendar', date=date))


def _image_still_referenced(image_path):
    return (
        AppPunch.query.filter_by(image_path=image_path).count() > 0
        or OfficialPunch.query.filter_by(image_path=image_path).count() > 0
    )


def _parse_time(val):
    val = val.strip()
    if not val:
        return None
    return datetime.strptime(val, '%H:%M').time()


def _parse_total(val):
    val = val.strip()
    if not val:
        return None
    h, m = val.split(':')
    return int(h) * 60 + int(m)
