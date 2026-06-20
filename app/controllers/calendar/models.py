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


def check_discrepancies(app_by_date, official_by_date):
    """
    Compare app vs official punch times for each date that appears in both sources.

    Returns a dict keyed by date. Each value is a list of issue dicts:
        {'type': 'in'|'out', 'app': time|None, 'official': time|None, 'delta_minutes': int|None}

    Only dates where both sources have a record are compared.
    """
    result = {}
    all_dates = set(app_by_date.keys()) | set(official_by_date.keys())

    for date in sorted(all_dates):
        ap = app_by_date.get(date)
        op = official_by_date.get(date)

        if not ap or not op:
            continue

        day_issues = []
        for label, app_time, off_time in [
            ('in',  ap.punch_in,  op.punch_in),
            ('out', ap.punch_out, op.punch_out),
        ]:
            if app_time and off_time:
                delta = _delta_minutes(app_time, off_time)
                if delta != 0:
                    day_issues.append({
                        'type':          label,
                        'app':           app_time,
                        'official':      off_time,
                        'delta_minutes': delta,
                    })
            elif app_time and not off_time:
                day_issues.append({'type': label, 'app': app_time, 'official': None, 'delta_minutes': None})
            elif off_time and not app_time:
                day_issues.append({'type': label, 'app': None, 'official': off_time, 'delta_minutes': None})

        if day_issues:
            result[date] = day_issues

    return result


def get_daily_summaries(app_by_date, official_by_date):
    """
    Per-day summary of scheduled time, OCR-scraped daily total, and calculated total.

    Returns a dict keyed by date:
        {
            'scheduled_time':     time | None,
            'ocr_total_minutes':  int | None,
            'calc_total_minutes': int | None,
            'total_mismatch':     bool,
        }
    """
    result = {}
    all_dates = set(app_by_date.keys()) | set(official_by_date.keys())

    for date in all_dates:
        ap = app_by_date.get(date)
        op = official_by_date.get(date)

        scheduled = ap.scheduled_time if ap else None

        # Prefer official total; fall back to app total
        ocr_total = None
        if op and op.daily_total_minutes is not None:
            ocr_total = op.daily_total_minutes
        elif ap and ap.daily_total_minutes is not None:
            ocr_total = ap.daily_total_minutes

        # Calculate total from the official source (authoritative); fall back to app
        ref = op or ap
        calc_total = None
        if ref and ref.punch_in and ref.punch_out:
            effective_in = ref.punch_in
            if scheduled and effective_in < scheduled:
                effective_in = scheduled
            calc_total = _delta_minutes(ref.punch_out, effective_in)

        result[date] = {
            'scheduled_time':     scheduled,
            'ocr_total_minutes':  ocr_total,
            'calc_total_minutes': calc_total,
            'total_mismatch': (
                ocr_total is not None
                and calc_total is not None
                and ocr_total != calc_total
            ),
        }

    return result


def _delta_minutes(t1, t2):
    """Signed difference in whole minutes: t1 − t2."""
    return (t1.hour * 60 + t1.minute) - (t2.hour * 60 + t2.minute)
