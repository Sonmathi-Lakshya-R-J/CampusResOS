
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from functools import wraps

from flask import jsonify, session


def serialize_time(value):
    """Convert MySQL TIME values into HH:MM:SS strings."""
    if value is None:
        return None

    if hasattr(value, "total_seconds"):
        total_seconds = int(value.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    if hasattr(value, "strftime"):
        return value.strftime("%H:%M:%S")

    return str(value)


def booking_time_error(booking_date, slot_start):
    """Reject past dates and slots that have already started in India."""
    now = datetime.now(ZoneInfo("Asia/Kolkata"))

    if booking_date < now.date():
        return "Bookings cannot be made for a past date."

    start_text = serialize_time(slot_start)
    start_time = datetime.strptime(start_text[:8], "%H:%M:%S").time()

    if booking_date == now.date() and start_time <= now.time().replace(tzinfo=None):
        return "This time slot has already started. Please select a future slot."

    return None


def faculty_schedule_conflict(cur, faculty_id, booking_date, slot):
    """Return a conflict message if this faculty member is already occupied."""

    day_name = booking_date.strftime("%A").upper()

    cur.execute("""
        SELECT
            COALESCE(c.room_name, c.room_code, 'Unassigned classroom') AS room_name,
            COALESCE(te.activity_name, te.activity_type) AS activity_name
        FROM timetable_entries te
        JOIN timetables t ON t.timetable_id = te.timetable_id
        JOIN time_slots ts ON ts.slot_id = te.slot_id
        LEFT JOIN classrooms c ON c.classroom_id = te.classroom_id
        WHERE te.faculty_id = %s
          AND te.day_of_week = %s
          AND t.status = 'ACTIVE'
          AND t.effective_from <= %s
          AND (t.effective_to IS NULL OR t.effective_to >= %s)
          AND ts.start_time < %s
          AND ts.end_time > %s
        LIMIT 1
    """, (
        faculty_id, day_name, booking_date, booking_date,
        slot["end_time"], slot["start_time"]
    ))

    conflict = cur.fetchone()

    if conflict:
        return (
            f"You already have a class in {conflict['room_name']} "
            f"at this time ({conflict['activity_name']})."
        )

    cur.execute("""
        SELECT c.room_name
        FROM bookings b
        JOIN classrooms c ON c.classroom_id = b.classroom_id
        JOIN time_slots ts ON ts.slot_id = b.slot_id
        WHERE b.faculty_id = %s
          AND b.booking_date = %s
          AND b.status = 'CONFIRMED'
          AND ts.start_time < %s
          AND ts.end_time > %s
        LIMIT 1
    """, (
        faculty_id, booking_date,
        slot["end_time"], slot["start_time"]
    ))

    conflict = cur.fetchone()

    if conflict:
        return (
            f"You already have a confirmed booking in "
            f"{conflict['room_name']} at this time."
        )

    return None


def room_has_schedule_conflict(cur, room_id, booking_date, slot):
    """Check whether a room has a regular class or confirmed booking."""

    day_name = booking_date.strftime("%A").upper()

    cur.execute("""
        SELECT te.entry_id
        FROM timetable_entries te
        JOIN timetables t ON t.timetable_id = te.timetable_id
        JOIN time_slots ts ON ts.slot_id = te.slot_id
        WHERE te.classroom_id = %s
          AND te.day_of_week = %s
          AND t.status = 'ACTIVE'
          AND t.effective_from <= %s
          AND (t.effective_to IS NULL OR t.effective_to >= %s)
          AND ts.start_time < %s
          AND ts.end_time > %s
        LIMIT 1
    """, (
        room_id, day_name, booking_date, booking_date,
        slot["end_time"], slot["start_time"]
    ))

    if cur.fetchone():
        return True

    cur.execute("""
        SELECT b.booking_id
        FROM bookings b
        JOIN time_slots ts ON ts.slot_id = b.slot_id
        WHERE b.classroom_id = %s
          AND b.booking_date = %s
          AND b.status = 'CONFIRMED'
          AND ts.start_time < %s
          AND ts.end_time > %s
        LIMIT 1
    """, (
        room_id, booking_date,
        slot["end_time"], slot["start_time"]
    ))

    return cur.fetchone() is not None


def db_error_message(exc):
    return str(exc) if os.getenv("FLASK_DEBUG") == "1" else "Database operation failed."


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Please log in first."}), 401
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Please log in first."}), 401
        if session.get("role") != "ADMIN":
            return jsonify({"error": "Admin access required."}), 403
        return fn(*args, **kwargs)
    return wrapper
