from datetime import timedelta


def get_week_days(week_start, week_end):
    days = []
    d = week_start
    while d <= week_end:
        days.append({
            'date':        d,
            'label':       d.strftime('%A'),            # "Monday"
            'short':       d.strftime('%a'),             # "Mon"
            'date_str':    d.strftime('%Y-%m-%d'),
            'collapse_id': 'day-' + d.strftime('%Y%m%d'),
        })
        d += timedelta(days=1)
    return days
