from flask import Blueprint, render_template
from datetime import datetime, timedelta
from .models import get_week_dates

calendar_bp = Blueprint('calendar', __name__)

@calendar_bp.route('/cal')
@calendar_bp.route('/cal/<date>')
def show_calendar(date=None):
    if date:
        week_end_date = datetime.strptime(date, '%Y-%m-%d')
    else:
        today = datetime.today()
        week_end_date = today + timedelta((5-today.weekday()) % 7)
    week_end_date_str = week_end_date.strftime('%Y-%m-%d')
    formatted_week_end_date = week_end_date.strftime('%m/%d/%Y')
    week_dates = get_week_dates(week_end_date_str)
    day_ids = {
        'Sun': 'flush-collapseSun',
        'Mon': 'flush-collapseMon',
        'Tue': 'flush-collapseTue',
        'Wed': 'flush-collapseWed',
        'Thu': 'flush-collapseThu',
        'Fri': 'flush-collapseFri',
        'Sat': 'flush-collapseSat'
    }
    return render_template(
        'calendar/cal-weekly.html', 
        week_dates=week_dates, 
        week_end_date=week_end_date_str,
        formatted_week_end_date=formatted_week_end_date,
        day_ids=day_ids,
        datetime=datetime,
        timedelta=timedelta
    )