from datetime import timedelta


def get_week_days(week_start, week_end):
    days = []
    d = week_start
    while d <= week_end:
        days.append({
            'date':        d,
            'label':       d.strftime('%A'),
            'short':       d.strftime('%a'),
            'date_str':    d.strftime('%Y-%m-%d'),
            'collapse_id': 'day-' + d.strftime('%Y%m%d'),
        })
        d += timedelta(days=1)
    return days


def check_discrepancies(punches_by_date):
    """
    Compare app vs official punches for each date.

    Returns a dict keyed by date. Each value is a list of dicts:
        {'type': 'in'|'out', 'app': time|None, 'official': time|None, 'delta_minutes': int}

    A discrepancy exists when both sources have a punch of the same type but the
    times differ, OR when one source has a punch and the other doesn't.
    Days with no discrepancies are not included in the result.
    """
    result = {}

    for date, punches in punches_by_date.items():
        app      = {p.type: p for p in punches if p.source == 'app'}
        official = {p.type: p for p in punches if p.source == 'official'}

        if not app or not official:
            # Only one source uploaded — nothing to cross-check yet
            continue

        day_issues = []
        for punch_type in ('in', 'out'):
            app_punch      = app.get(punch_type)
            official_punch = official.get(punch_type)

            if app_punch and official_punch:
                delta = _delta_minutes(app_punch.time, official_punch.time)
                if delta != 0:
                    day_issues.append({
                        'type':          punch_type,
                        'app':           app_punch.time,
                        'official':      official_punch.time,
                        'delta_minutes': delta,
                    })
            elif app_punch and not official_punch:
                day_issues.append({
                    'type':          punch_type,
                    'app':           app_punch.time,
                    'official':      None,
                    'delta_minutes': None,
                })
            elif official_punch and not app_punch:
                day_issues.append({
                    'type':          punch_type,
                    'app':           None,
                    'official':      official_punch.time,
                    'delta_minutes': None,
                })

        if day_issues:
            result[date] = day_issues

    return result


def _delta_minutes(t1, t2):
    """Signed difference in whole minutes: t1 − t2."""
    return (t1.hour * 60 + t1.minute) - (t2.hour * 60 + t2.minute)
