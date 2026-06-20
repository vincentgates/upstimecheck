from collections import defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.db import db, Punch
from .models import get_week_days, check_discrepancies, get_daily_summaries

calendar_bp = Blueprint('calendar', __name__)


@calendar_bp.route('/cal')
@calendar_bp.route('/cal/<date>')
def show_calendar(date=None):
    if date:
        try:
            week_end = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            today = datetime.today().date()
            week_end = today + timedelta((5 - today.weekday()) % 7)
    else:
        today = datetime.today().date()
        week_end = today + timedelta((5 - today.weekday()) % 7)

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


@calendar_bp.route('/punch/<int:punch_id>/delete', methods=['POST'])
def delete_punch(punch_id):
    punch = Punch.query.get_or_404(punch_id)
    date_str = punch.date.strftime('%Y-%m-%d')
    db.session.delete(punch)
    db.session.commit()
    flash('Punch deleted.', 'success')
    return redirect(url_for('calendar.show_calendar', date=date_str))
