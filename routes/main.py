from datetime import date, timedelta
from collections import Counter, defaultdict
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from database import db
from models import Medication, MedicationLog

main_bp = Blueprint("main", __name__)
DEMO_EMAIL = "demo@meditrack.app"
DEMO_PASSWORD = "Demo123"


def require_demo():
    return session.get("demo_user") is True


def status_counts():
    return Counter(m.status for m in Medication.query.all())


def record_status(med, status):
    med.status = status
    today_log = MedicationLog.query.filter_by(medication_id=med.id, log_date=date.today()).first()
    if today_log:
        today_log.status = status
    else:
        db.session.add(MedicationLog(medication_id=med.id, log_date=date.today(), medicine_name=med.name,
                                     dosage=med.dosage, scheduled_time=med.scheduled_time, status=status))
    db.session.commit()


@main_bp.before_app_request
def protect_app():
    public = {"main.landing", "main.login", "static"}
    if request.endpoint not in public and request.endpoint and not require_demo():
        return redirect(url_for("main.login"))


@main_bp.route("/")
def landing():
    return render_template("landing.html")


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        demo_button = request.form.get("demo") == "true"
        if demo_button or (request.form.get("email") == DEMO_EMAIL and request.form.get("password") == DEMO_PASSWORD):
            session["demo_user"] = True
            flash("Welcome back to your demo workspace.", "success")
            return redirect(url_for("main.dashboard"))
        flash("Invalid credentials. Please use the demo account.", "error")
    return render_template("login.html", demo_email=DEMO_EMAIL, demo_password=DEMO_PASSWORD)


@main_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


@main_bp.route("/dashboard")
def dashboard():
    meds = Medication.query.order_by(Medication.scheduled_time).all()
    counts = status_counts()
    taken = counts.get("Taken", 0)
    total = max(len(meds), 1)
    return render_template("dashboard.html", meds=meds, today=date.today(), counts=counts,
                           progress=round(taken / total * 100), recent=MedicationLog.query.order_by(MedicationLog.created_at.desc()).limit(6).all())


@main_bp.route("/medications", methods=["GET", "POST"])
def medications():
    if request.method == "POST":
        med = Medication(name=request.form["name"], dosage=request.form["dosage"], frequency=request.form["frequency"],
                         scheduled_time=request.form["scheduled_time"], start_date=date.fromisoformat(request.form["start_date"]),
                         end_date=date.fromisoformat(request.form["end_date"]) if request.form.get("end_date") else None,
                         notes=request.form.get("notes", ""), status=request.form.get("status", "Upcoming"))
        db.session.add(med); db.session.commit(); flash(f"{med.name} was added.", "success")
        return redirect(url_for("main.medications"))
    return render_template("medications.html", meds=Medication.query.order_by(Medication.scheduled_time).all(), today=date.today())


@main_bp.route("/medications/<int:med_id>/edit", methods=["POST"])
def edit_medication(med_id):
    med = Medication.query.get_or_404(med_id)
    for field in ["name", "dosage", "frequency", "scheduled_time", "notes", "status"]:
        setattr(med, field, request.form.get(field, getattr(med, field)))
    med.start_date = date.fromisoformat(request.form["start_date"])
    med.end_date = date.fromisoformat(request.form["end_date"]) if request.form.get("end_date") else None
    db.session.commit(); flash(f"{med.name} was updated.", "success")
    return redirect(url_for("main.medications"))


@main_bp.route("/medications/<int:med_id>/delete", methods=["POST"])
def delete_medication(med_id):
    med = Medication.query.get_or_404(med_id)
    db.session.delete(med); db.session.commit(); flash("Medication deleted.", "success")
    return redirect(url_for("main.medications"))


@main_bp.route("/medications/<int:med_id>/status/<status>", methods=["POST"])
def set_status(med_id, status):
    med = Medication.query.get_or_404(med_id)
    record_status(med, status.title())
    flash(f"{med.name} marked as {status}.", "success")
    return redirect(request.referrer or url_for("main.dashboard"))


@main_bp.route("/history")
def history():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    query = MedicationLog.query
    if q: query = query.filter(MedicationLog.medicine_name.ilike(f"%{q}%"))
    if status: query = query.filter_by(status=status)
    return render_template("history.html", logs=query.order_by(MedicationLog.log_date.desc(), MedicationLog.scheduled_time).all(), q=q, selected_status=status)


@main_bp.route("/statistics")
def statistics():
    return render_template("statistics.html")


@main_bp.route("/api/statistics")
def api_statistics():
    logs = MedicationLog.query.all(); today = date.today()
    weekly = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_logs = [l for l in logs if l.log_date == day and l.status != "Upcoming"]
        pct = round(sum(1 for l in day_logs if l.status == "Taken") / max(len(day_logs), 1) * 100)
        weekly.append({"label": day.strftime("%a"), "value": pct})
    monthly = [82, 88, 84, 91, 89, 94]
    counts = Counter(l.status for l in logs)
    completed = round(counts.get("Taken", 0) / max(counts.get("Taken", 0) + counts.get("Missed", 0), 1) * 100)
    return jsonify({"weekly": weekly, "monthly": monthly, "taken": counts.get("Taken", 0), "missed": counts.get("Missed", 0), "completion": completed})


@main_bp.route("/settings")
def settings():
    return render_template("settings.html")
