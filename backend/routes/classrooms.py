from datetime import date

from flask import Blueprint, current_app, jsonify, request, session

from db import get_connection
from services.booking_helpers import (
    serialize_time,
    booking_time_error,
    faculty_schedule_conflict,
    room_has_schedule_conflict,
    db_error_message,
    login_required,
)

bp = Blueprint("classrooms", __name__)


@bp.get("/api/rooms")
@login_required
def rooms():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT classroom_id, room_code, room_name, capacity, room_type
            FROM classrooms
            WHERE status = 'AVAILABLE'
            ORDER BY room_code
        """)
        return jsonify({"rooms": cur.fetchall()})
    finally:
        cur.close()
        conn.close()



@bp.get("/api/time-slots")
@login_required
def list_time_slots():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT slot_id, slot_label, start_time, end_time, slot_order
            FROM time_slots
            ORDER BY slot_order
        """)
        slots = cur.fetchall()

        for slot in slots:
            for field in ("start_time", "end_time"):
                slot[field] = serialize_time(slot[field])

        return jsonify({"success": True, "slots": slots})
    finally:
        cur.close()
        conn.close()



@bp.get("/api/available-rooms")
@login_required
def available_rooms():
    """List rooms not already booked for the requested date and slot."""
    if session.get("role") != "FACULTY":
        return jsonify({"error": "Only faculty can search for booking availability."}), 403

    try:
        booking_date = date.fromisoformat(request.args.get("booking_date", ""))
        slot_id = int(request.args.get("slot_id", ""))
    except (ValueError, TypeError):
        return jsonify({"error": "A valid booking_date and slot_id are required."}), 400

    if booking_date < date.today():
        return jsonify({"error": "Bookings cannot be searched for a past date."}), 400

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT slot_id, slot_label, start_time, end_time FROM time_slots WHERE slot_id = %s", (slot_id,))
        slot = cur.fetchone()
        if not slot:
            return jsonify({"error": "Invalid time slot."}), 400

        time_error = booking_time_error(booking_date, slot["start_time"])
        if time_error:
            return jsonify({"error": time_error}), 400



        cur.execute(
            "SELECT faculty_id FROM faculty WHERE user_id = %s",
            (session["user_id"],)
        )
        faculty = cur.fetchone()

        if not faculty:
            return jsonify({"error": "Faculty record not found."}), 403

        conflict_message = faculty_schedule_conflict(
            cur, faculty["faculty_id"], booking_date, slot
        )

        if conflict_message:
            return jsonify({"error": conflict_message}), 409




        cur.execute("""
            SELECT classroom_id, room_code, room_name, capacity, room_type
            FROM classrooms
            WHERE status = 'AVAILABLE'
            ORDER BY room_code
        """)

        all_rooms = cur.fetchall()

        rooms = [
            room for room in all_rooms
            if not room_has_schedule_conflict(
                cur, room["classroom_id"], booking_date, slot
            )
        ]

        return jsonify({
            "booking_date": booking_date.isoformat(),
            "slot": {
                "slot_id": slot["slot_id"],
                "slot_label": slot["slot_label"],
                "start_time": str(slot["start_time"]),
                "end_time": str(slot["end_time"]),
            },
            "rooms": rooms,
        })


        # cur.execute("""
        #     SELECT c.classroom_id, c.room_code, c.room_name, c.capacity, c.room_type
        #     FROM classrooms c
        #     WHERE c.status = 'AVAILABLE'
        #       AND NOT EXISTS (
        #           SELECT 1
        #           FROM bookings b
        #           WHERE b.classroom_id = c.classroom_id
        #             AND b.booking_date = %s
        #             AND b.slot_id = %s
        #             AND b.status = 'CONFIRMED'
        #       )
        #     ORDER BY c.room_code
        # """, (booking_date, slot_id))
        # rooms = cur.fetchall()
        # return jsonify({
        #     "booking_date": booking_date.isoformat(),
        #     "slot": {
        #         "slot_id": slot["slot_id"],
        #         "slot_label": slot["slot_label"],
        #         "start_time": str(slot["start_time"]),
        #         "end_time": str(slot["end_time"]),
        #     },
        #     "rooms": rooms,
        # })
    except Exception as exc:
        current_app.logger.exception("Could not check classroom availability")
        return jsonify({"error": db_error_message(exc)}), 500
    finally:
        cur.close()
        conn.close()
