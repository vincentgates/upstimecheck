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
    """One record per worked day — UPS official time system (web portal)."""
    __tablename__ = 'official_punches'

    id                  = db.Column(db.Integer, primary_key=True)
    date                = db.Column(db.Date,    nullable=False)
    punch_in            = db.Column(db.Time)
    punch_out           = db.Column(db.Time)
    daily_total_minutes = db.Column(db.Integer)
    raw_ocr_text        = db.Column(db.Text)
    confidence          = db.Column(db.Float)
    image_path          = db.Column(db.String(255))
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<OfficialPunch {self.date} in={self.punch_in} out={self.punch_out}>'
