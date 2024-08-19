from datetime import datetime, timedelta

def get_week_dates(week_end_date):
    end_date = datetime.strptime(week_end_date, '%Y-%m-%d')
    start_date = end_date - timedelta(days=6)
    return [(start_date + timedelta(days=i)).strftime('%a %m/%d/%Y') for i in range(7)]