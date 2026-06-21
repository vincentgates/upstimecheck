from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class AppPunch(db.Model):
    """One record per worked day — UPS handheld terminal clock-in screenshots."""
    __tablename__ = 'app_punches'

    id                  = db.Column(db.Integer, primary_key=True)
    date                = db.Column(db.Date,    nullable=False)
    punch_in            = db.Column(db.Time)
    punch_out           = db.Column(db.Time)
    scheduled_time      = db.Column(db.Time)
    daily_total_minutes = db.Column(db.Integer)
    raw_ocr_text        = db.Column(db.Text)
    confidence          = db.Column(db.Float)
    image_path          = db.Column(db.String(255))
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<AppPunch {self.date} in={self.punch_in} out={self.punch_out}>'


class OfficialPunch(db.Model):
    """One record per calendar day — UPS official time system (web portal).

    Every day in the weekly screenshot is stored, including No Card days.
    pay_code is 'PAY ACTUAL' for worked days and 'No Card' for days off.
    punch_in / punch_out are null for No Card days.
    corrected is True when the official system asterisked the start time
    (footnote: '*Indicates late for that day').
    """
    __tablename__ = 'official_punches'

    id                  = db.Column(db.Integer, primary_key=True)
    date                = db.Column(db.Date,    nullable=False)
    pay_code            = db.Column(db.String(20))    # 'PAY ACTUAL' | 'No Card'
    gross_pay           = db.Column(db.Float)         # e.g. 132.53
    punch_in            = db.Column(db.Time)          # start_time; null for No Card
    punch_out           = db.Column(db.Time)          # end_time;   null for No Card
    pay_rate            = db.Column(db.Float)         # e.g. 0.00
    daily_total_minutes = db.Column(db.Integer)       # total_hours × 60; 0 for No Card
    corrected           = db.Column(db.Boolean, nullable=False, default=False)
    raw_ocr_text        = db.Column(db.Text)
    confidence          = db.Column(db.Float)
    image_path          = db.Column(db.String(255))
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<OfficialPunch {self.date} {self.pay_code} in={self.punch_in} out={self.punch_out}>'
