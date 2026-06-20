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


@calendar_bp.route('/cal/<date>/edit/<source>', methods=['POST'])
def edit_punch(date, source):
    Model = _SOURCE_MODEL.get(source)
    if not Model:
        flash('Invalid source.', 'danger')
        return redirect(url_for('calendar.show_calendar', date=date))

    try:
        target_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date.', 'danger')
        return redirect(url_for('calendar.show_calendar'))

    p = Model.query.filter_by(date=target_date).first()
    if not p:
        flash('Record not found.', 'warning')
        return redirect(url_for('calendar.show_calendar', date=date))

    try:
        p.punch_in  = _parse_time(request.form.get('punch_in',  ''))
        p.punch_out = _parse_time(request.form.get('punch_out', ''))
        p.daily_total_minutes = _parse_total(request.form.get('daily_total', ''))
        if source == 'app':
            p.scheduled_time = _parse_time(request.form.get('scheduled_time', ''))
    except ValueError as e:
        flash(f'Invalid value: {e}', 'warning')
        return redirect(url_for('calendar.show_calendar', date=date))

    db.session.commit()
    flash('Record updated.', 'success')
    return redirect(url_for('calendar.show_calendar', date=date))


@calendar_bp.route('/cal/<date>/delete/<source>', methods=['POST'])
def delete_punch(date, source):
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
