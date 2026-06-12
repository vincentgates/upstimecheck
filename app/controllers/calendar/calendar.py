from collections import defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, render_template

from app.db import Punch
from .models import get_week_days

calendar_bp = Blueprint('calendar', __name__)


@calendar_bp.route('/cal')
@calendar_bp.route('/cal/<date>')
def show_calendar(date=None):
    if date:
        week_end = datetime.strptime(date, '%Y-%m-%d').date()
    else:
        today = datetime.today().date()
        week_end = today + timedelta((5 - today.weekday()) % 7)  # Saturday of current week

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

    return render_template(
        'calendar/cal-weekly.html',
        days=days,
        punches_by_date=punches_by_date,
        week_start=week_start,
        week_end=week_end,
        formatted_week_end=week_end.strftime('%m/%d/%Y'),
        prev_week=(week_end - timedelta(days=7)).strftime('%Y-%m-%d'),
        next_week=(week_end + timedelta(days=7)).strftime('%Y-%m-%d'),
    )
