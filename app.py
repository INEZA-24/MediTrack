from datetime import date, timedelta
from flask import Flask
from config import Config
from database import db
from models import Medication, MedicationLog
from routes.main import main_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    app.register_blueprint(main_bp)
    with app.app_context():
        db.create_all()
        seed_demo_data()
    return app


def seed_demo_data():
    if Medication.query.count():
        return
    today = date.today()
    medicines = [
        ("Paracetamol", "500 mg", "Twice daily", "08:00", -12, 14, "Take after breakfast.", "Taken"),
        ("Vitamin C", "1000 mg", "Once daily", "09:30", -30, 60, "Supports immune health.", "Upcoming"),
        ("Ibuprofen", "200 mg", "As needed", "13:00", -5, 5, "Avoid on an empty stomach.", "Missed"),
        ("Amoxicillin", "250 mg", "Three times daily", "18:00", -3, 4, "Finish the full course.", "Taken"),
        ("Metformin", "500 mg", "Once daily", "21:00", -45, 120, "Evening dose with meal.", "Upcoming"),
    ]
    for name, dosage, freq, time, start, end, notes, status in medicines:
        med = Medication(name=name, dosage=dosage, frequency=freq, scheduled_time=time,
                         start_date=today + timedelta(days=start), end_date=today + timedelta(days=end),
                         notes=notes, status=status)
        db.session.add(med)
        db.session.flush()
        for offset in range(-13, 1):
            if offset == 0:
                log_status = status
            elif (med.id + offset) % 6 == 0:
                log_status = "Missed"
            elif (med.id + offset) % 5 == 0:
                log_status = "Upcoming"
            else:
                log_status = "Taken"
            db.session.add(MedicationLog(medication_id=med.id, log_date=today + timedelta(days=offset),
                                         medicine_name=name, dosage=dosage, scheduled_time=time, status=log_status))
    db.session.commit()


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
