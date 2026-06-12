from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Punch(db.Model):
    __tablename__ = 'punches'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    type = db.Column(db.String(3), nullable=False)   # 'in' or 'out'
    source = db.Column(db.String(10), nullable=False) # 'app' or 'official'
    raw_ocr_text = db.Column(db.Text)
    confidence = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Punch {self.date} {self.time} {self.type} [{self.source}]>'
