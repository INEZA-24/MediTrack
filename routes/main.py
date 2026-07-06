from collections import Counter
from datetime import date, datetime, time, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from database import db
from models import Medication, MedicationLog

main_bp = Blueprint("main", __name__)
DEMO_EMAIL = "demo@meditrack.app"
DEMO_PASSWORD = "Demo123"
FINAL_STATUSES = {"Taken", "Missed"}
ACTIVE_STATUSES = {"Upcoming", "Due Now", "Overdue"}
REMINDER_WINDOW_MINUTES = 15
OVERDUE_AFTER_MINUTES = 60


def require_demo():
    return session.get("demo_user") is True


def parse_scheduled_time(value):
    hour, minute = [int(part) for part in value.split(":")]
    return time(hour=hour, minute=minute)


def scheduled_datetime(log):
    return datetime.combine(log.log_date, parse_scheduled_time(log.scheduled_time))


def active_medications(day=None):
    selected_day = day or date.today()
    return Medication.query.filter(
        Medication.start_date <= selected_day,
        db.or_(Medication.end_date.is_(None), Medication.end_date >= selected_day),
    ).order_by(Medication.scheduled_time).all()


def ensure_daily_logs(day=None):
    selected_day = day or date.today()
    created = False
    for med in active_medications(selected_day):
        existing = MedicationLog.query.filter_by(medication_id=med.id, log_date=selected_day).first()
        if existing:
            existing.medicine_name = med.name
            existing.dosage = med.dosage
            existing.scheduled_time = med.scheduled_time
            continue
        db.session.add(MedicationLog(
            medication_id=med.id,
            log_date=selected_day,
            medicine_name=med.name,
            dosage=med.dosage,
            scheduled_time=med.scheduled_time,
            status="Upcoming",
        ))
        created = True
    if created:
        db.session.commit()
    update_due_statuses(selected_day)


def update_due_statuses(day=None):
    selected_day = day or date.today()
    now = datetime.now()
    changed = False
    todays_logs = MedicationLog.query.filter_by(log_date=selected_day).all()
    for log in todays_logs:
        if log.status in FINAL_STATUSES:
            continue
        scheduled_at = scheduled_datetime(log)
        minutes_from_dose = (now - scheduled_at).total_seconds() / 60
        if minutes_from_dose >= OVERDUE_AFTER_MINUTES:
            log.status = "Missed"
            changed = True
        elif minutes_from_dose >= 0:
            log.status = "Due Now"
            changed = True
        else:
            log.status = "Upcoming"
            changed = True
    if changed:
        db.session.commit()


def today_logs():
    ensure_daily_logs()
    return MedicationLog.query.filter_by(log_date=date.today()).order_by(MedicationLog.scheduled_time).all()


def status_counts(logs):
    return Counter(log.status for log in logs)


def update_medication_snapshot(log):
    med = Medication.query.get(log.medication_id)
    if med:
        med.status = log.status


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
        valid_credentials = request.form.get("email") == DEMO_EMAIL and request.form.get("password") == DEMO_PASSWORD
        if demo_button or valid_credentials:
            session["demo_user"] = True
            ensure_daily_logs()
            flash("Welcome back. Today's medication checklist is ready.", "success")
            return redirect(url_for("main.dashboard"))
        flash("Invalid credentials. Please use the demo account.", "error")
    return render_template("login.html", demo_email=DEMO_EMAIL, demo_password=DEMO_PASSWORD)


@main_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


@main_bp.route("/dashboard")
def dashboard():
    logs = today_logs()
    counts = status_counts(logs)
    completed = counts.get("Taken", 0)
    total = max(len(logs), 1)
    next_dose = next((log for log in logs if log.status in ACTIVE_STATUSES), None)
    return render_template(
        "dashboard.html",
        logs=logs,
        today=date.today(),
        counts=counts,
        progress=round(completed / total * 100),
        next_dose=next_dose,
        recent=MedicationLog.query.order_by(MedicationLog.created_at.desc()).limit(6).all(),
    )


@main_bp.route("/medications", methods=["GET", "POST"])
def medications():
    if request.method == "POST":
        med = Medication(
            name=request.form["name"],
            dosage=request.form["dosage"],
            frequency=request.form["frequency"],
            scheduled_time=request.form["scheduled_time"],
            start_date=date.fromisoformat(request.form["start_date"]),
            end_date=date.fromisoformat(request.form["end_date"]) if request.form.get("end_date") else None,
            notes=request.form.get("notes", ""),
            status="Upcoming",
        )
        db.session.add(med)
        db.session.commit()
        ensure_daily_logs()
        flash(f"{med.name} was added to today's schedule.", "success")
        return redirect(url_for("main.medications"))
    ensure_daily_logs()
    return render_template("medications.html", meds=Medication.query.order_by(Medication.scheduled_time).all(), today=date.today())


@main_bp.route("/medications/<int:med_id>/edit", methods=["POST"])
def edit_medication(med_id):
    med = Medication.query.get_or_404(med_id)
    for field in ["name", "dosage", "frequency", "scheduled_time", "notes"]:
        setattr(med, field, request.form.get(field, getattr(med, field)))
    med.start_date = date.fromisoformat(request.form["start_date"])
    med.end_date = date.fromisoformat(request.form["end_date"]) if request.form.get("end_date") else None
    db.session.commit()
    ensure_daily_logs()
    flash(f"{med.name} was updated and today's checklist was refreshed.", "success")
    return redirect(url_for("main.medications"))


@main_bp.route("/medications/<int:med_id>/delete", methods=["POST"])
def delete_medication(med_id):
    med = Medication.query.get_or_404(med_id)
    db.session.delete(med)
    db.session.commit()
    flash("Medication deleted.", "success")
    return redirect(url_for("main.medications"))


@main_bp.route("/dose/<int:log_id>/status/<status>", methods=["POST"])
def set_dose_status(log_id, status):
    log = MedicationLog.query.get_or_404(log_id)
    normalized_status = status.title()
    if normalized_status not in FINAL_STATUSES:
        flash("That dose status is not supported.", "error")
        return redirect(request.referrer or url_for("main.dashboard"))
    log.status = normalized_status
    update_medication_snapshot(log)
    db.session.commit()
    flash(f"{log.medicine_name} marked as {normalized_status.lower()} for today.", "success")
    return redirect(request.referrer or url_for("main.dashboard"))


@main_bp.route("/medications/<int:med_id>/status/<status>", methods=["POST"])
def set_status(med_id, status):
    ensure_daily_logs()
    log = MedicationLog.query.filter_by(medication_id=med_id, log_date=date.today()).first_or_404()
    return set_dose_status(log.id, status)


@main_bp.route("/history")
def history():
    ensure_daily_logs()
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    query = MedicationLog.query
    if q:
        query = query.filter(MedicationLog.medicine_name.ilike(f"%{q}%"))
    if status:
        query = query.filter_by(status=status)
    return render_template(
        "history.html",
        logs=query.order_by(MedicationLog.log_date.desc(), MedicationLog.scheduled_time).all(),
        q=q,
        selected_status=status,
    )


@main_bp.route("/statistics")
def statistics():
    ensure_daily_logs()
    return render_template("statistics.html")


@main_bp.route("/api/statistics")
def api_statistics():
    ensure_daily_logs()
    logs = MedicationLog.query.all()
    today = date.today()
    weekly = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_logs = [log for log in logs if log.log_date == day]
        pct = round(sum(1 for log in day_logs if log.status == "Taken") / max(len(day_logs), 1) * 100)
        weekly.append({"label": day.strftime("%a"), "value": pct})
    monthly = []
    for i in range(5, -1, -1):
        month_anchor = today.replace(day=1) - timedelta(days=30 * i)
        month_logs = [log for log in logs if log.log_date.strftime("%Y-%m") == month_anchor.strftime("%Y-%m")]
        pct = round(sum(1 for log in month_logs if log.status == "Taken") / max(len(month_logs), 1) * 100)
        monthly.append({"label": month_anchor.strftime("%b"), "value": pct})
    counts = Counter(log.status for log in logs)
    completed = round(counts.get("Taken", 0) / max(len(logs), 1) * 100)
    return jsonify({
        "weekly": weekly,
        "monthly": monthly,
        "taken": counts.get("Taken", 0),
        "missed": counts.get("Missed", 0),
        "completion": completed,
    })


@main_bp.route("/api/reminders")
def api_reminders():
    ensure_daily_logs()
    now = datetime.now()
    reminders = []
    for log in today_logs():
        if log.status in FINAL_STATUSES:
            continue
        scheduled_at = scheduled_datetime(log)
        minutes_until = round((scheduled_at - now).total_seconds() / 60)
        should_notify = log.status in {"Due Now", "Overdue"} or 0 <= minutes_until <= REMINDER_WINDOW_MINUTES
        reminders.append({
            "id": log.id,
            "medicine": log.medicine_name,
            "dosage": log.dosage,
            "time": log.scheduled_time,
            "status": log.status,
            "minutes_until": minutes_until,
            "should_notify": should_notify,
            "message": reminder_message(log, minutes_until),
        })
    return jsonify({"reminders": reminders})


def reminder_message(log, minutes_until):
    if log.status == "Due Now":
        return f"It is time to take {log.medicine_name} — {log.dosage}."
    if log.status == "Missed":
        return f"{log.medicine_name} was missed today."
    if minutes_until > 0:
        return f"{log.medicine_name} is due in {minutes_until} minutes."
    return f"{log.medicine_name} is due now."


@main_bp.route("/settings")
def settings():
    return render_template("settings.html")
