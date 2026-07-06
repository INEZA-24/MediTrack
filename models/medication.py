from datetime import date, datetime
from database import db

class Medication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    dosage = db.Column(db.String(80), nullable=False)
    frequency = db.Column(db.String(80), nullable=False)
    scheduled_time = db.Column(db.String(5), nullable=False)
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    end_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, default="")
    status = db.Column(db.String(20), nullable=False, default="Upcoming")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    logs = db.relationship("MedicationLog", backref="medication", cascade="all, delete-orphan", lazy=True)

    @property
    def is_active(self):
        today = date.today()
        return self.start_date <= today and (self.end_date is None or self.end_date >= today)

class MedicationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    medication_id = db.Column(db.Integer, db.ForeignKey("medication.id"), nullable=False)
    log_date = db.Column(db.Date, nullable=False, default=date.today)
    medicine_name = db.Column(db.String(120), nullable=False)
    dosage = db.Column(db.String(80), nullable=False)
    scheduled_time = db.Column(db.String(5), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
