import os
from collections import defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.db import db, Punch
from .models import get_week_days, check_discrepancies, get_daily_summaries

_UPLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'uploads', 'processed')
)

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

    # Always resolve to the Saturday that ends the week containing `given`,
    # regardless of which day of the week the URL date falls on.
    week_end = given + timedelta((5 - given.weekday()) % 7)

    week_start = week_end - timedelta(days=6)
    days = get_week_days(week_start, week_end)

    punches = (
        Punch.query
        .filter(Punch.date >= week_start, Punch.date <= week_end)
        .order_by(Punch.date, Punch.time)
        .all()
    )

    punches_by_date = defaultdict(list)
    for p in punches:
        punches_by_date[p.date].append(p)

    discrepancies   = check_discrepancies(punches_by_date)
    daily_summaries = get_daily_summaries(punches_by_date)

    return render_template(
        'calendar/cal-weekly.html',
        days=days,
        punches_by_date=punches_by_date,
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
    # ── Per-punch time edits ──────────────────────────────────────────────────
    punch_ids = request.form.getlist('punch_id')
    for pid in punch_ids:
        time_str = request.form.get(f'time_{pid}', '').strip()
        if not time_str:
            continue
        punch = Punch.query.get(int(pid))
        if punch:
            try:
                punch.time = datetime.strptime(time_str, '%H:%M').time()
            except ValueError:
                flash(f'Invalid time value "{time_str}" — skipped.', 'warning')

    # ── Day-level fields ───────────────────────────────────────────────────────
    try:
        target_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        target_date = None

    if target_date:
        sched_str    = request.form.get('scheduled_time',    '').strip()
        app_tot_str  = request.form.get('app_daily_total',   '').strip()
        off_tot_str  = request.form.get('official_daily_total', '').strip()

        new_sched = None
        if sched_str:
            try:
                new_sched = datetime.strptime(sched_str, '%H:%M').time()
            except ValueError:
                flash('Invalid scheduled time — use HH:MM.', 'warning')
                sched_str = None

        new_app_tot = None
        if app_tot_str:
            try:
                h, m = app_tot_str.split(':')
                new_app_tot = int(h) * 60 + int(m)
            except (ValueError, AttributeError):
                flash('Invalid Daily Total — use H:MM (e.g. 5:30).', 'warning')
                app_tot_str = None

        new_off_tot = None
        if off_tot_str:
            try:
                h, m = off_tot_str.split(':')
                new_off_tot = int(h) * 60 + int(m)
            except (ValueError, AttributeError):
                flash('Invalid Total Hours — use H:MM (e.g. 5:30).', 'warning')
                off_tot_str = None

        for p in Punch.query.filter_by(date=target_date).all():
            if sched_str is not None:
                p.scheduled_time = new_sched
            if p.source == 'app' and app_tot_str is not None:
                p.daily_total_minutes = new_app_tot
            if p.source == 'official' and off_tot_str is not None:
                p.daily_total_minutes = new_off_tot

    db.session.commit()
    flash('Punches updated.', 'success')
    return redirect(url_for('calendar.show_calendar', date=date))


@calendar_bp.route('/cal/<date>/delete', methods=['POST'])
def delete_day(date):
    try:
        target_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date.', 'danger')
        return redirect(url_for('calendar.show_calendar'))

    punches = Punch.query.filter_by(date=target_date).all()
    image_paths = {p.image_path for p in punches if p.image_path}

    for p in punches:
        db.session.delete(p)
    db.session.commit()

    for img in image_paths:
        full = os.path.join(_UPLOAD_DIR, img)
        if os.path.exists(full):
            os.remove(full)

    flash(f'All records for {target_date.strftime("%b %d")} deleted.', 'success')
    return redirect(url_for('calendar.show_calendar', date=date))
