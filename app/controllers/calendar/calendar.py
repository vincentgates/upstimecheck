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
