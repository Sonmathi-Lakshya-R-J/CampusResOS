from flask import Blueprint, current_app, jsonify, request, session

from db import get_connection
from services.booking_helpers import login_required, db_error_message, serialize_time

bp = Blueprint("faculty", __name__)


@bp.post("/api/faculty/schedule-change-requests")
@login_required
def create_schedule_change_request():
    """Let faculty submit a ticket to change an existing regular timetable entry."""
    if session.get("role") != "FACULTY":
        return jsonify({"error": "Faculty access required."}), 403

    payload = request.get_json(silent=True) or {}
    try:
        timetable_entry_id = int(payload.get("timetable_entry_id"))
        requested_slot_id = int(payload.get("requested_slot_id"))
    except (TypeError, ValueError):
        return jsonify({
            "error": "A valid timetable_entry_id and requested_slot_id are required."
        }), 400

    requested_day = str(payload.get("requested_day", "")).strip().upper()
    valid_days = {"MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"}
    if requested_day not in valid_days:
        return jsonify({"error": "Select a valid requested day."}), 400

    reason = str(payload.get("reason", "")).strip()
    if not reason or len(reason) > 500:
        return jsonify({"error": "Reason is required and must not exceed 500 characters."}), 400

    requested_classroom_id = payload.get("requested_classroom_id")
    if requested_classroom_id in (None, ""):
        requested_classroom_id = None
    else:
        try:
            requested_classroom_id = int(requested_classroom_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid requested classroom."}), 400

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT faculty_id FROM faculty WHERE user_id = %s", (session["user_id"],))
        faculty = cur.fetchone()
        if not faculty:
            return jsonify({"error": "Your account is not linked to a faculty record."}), 403

        # Only allow requests against this faculty member's active regular timetable.
        cur.execute("""
            SELECT te.entry_id, te.day_of_week, te.slot_id
            FROM timetable_entries te
            JOIN timetables t ON t.timetable_id = te.timetable_id
            WHERE te.entry_id = %s
              AND te.faculty_id = %s
              AND t.status = 'ACTIVE'
              AND t.effective_from <= CURDATE()
              AND (t.effective_to IS NULL OR t.effective_to >= CURDATE())
            LIMIT 1
        """, (timetable_entry_id, faculty["faculty_id"]))
        entry = cur.fetchone()
        if not entry:
            return jsonify({"error": "The selected timetable entry was not found in your active schedule."}), 404

        cur.execute("SELECT slot_id FROM time_slots WHERE slot_id = %s", (requested_slot_id,))
        if not cur.fetchone():
            return jsonify({"error": "The requested time slot does not exist."}), 400

        if requested_classroom_id is not None:
            cur.execute("""
                SELECT classroom_id FROM classrooms
                WHERE classroom_id = %s AND status = 'AVAILABLE'
            """, (requested_classroom_id,))
            if not cur.fetchone():
                return jsonify({"error": "The requested classroom is unavailable or does not exist."}), 400

        cur.execute("""
            INSERT INTO schedule_change_requests (
                faculty_id, timetable_entry_id, current_day, current_slot_id,
                requested_day, requested_slot_id, requested_classroom_id, reason
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            faculty["faculty_id"], entry["entry_id"], entry["day_of_week"],
            entry["slot_id"], requested_day, requested_slot_id,
            requested_classroom_id, reason
        ))
        ticket_id = cur.lastrowid
        conn.commit()
        return jsonify({
            "ok": True,
            "ticket_id": ticket_id,
            "status": "PENDING",
            "message": "Schedule-change ticket submitted for admin review."
        }), 201
    except Exception as exc:
        conn.rollback()
        current_app.logger.exception("Could not submit schedule-change ticket")
        return jsonify({"error": db_error_message(exc)}), 500
    finally:
        cur.close()
        conn.close()


@bp.get("/api/faculty/schedule-change-requests")
@login_required
def faculty_schedule_change_requests():
    """Return schedule-change tickets submitted by the logged-in faculty member."""
    if session.get("role") != "FACULTY":
        return jsonify({"error": "Faculty access required."}), 403

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT
                scr.ticket_id, scr.current_day,
                current_slot.slot_label AS current_slot_label,
                scr.requested_day,
                requested_slot.slot_label AS requested_slot_label,
                scr.reason, scr.status, scr.review_note,
                scr.created_at, scr.reviewed_at
            FROM schedule_change_requests scr
            JOIN faculty f ON f.faculty_id = scr.faculty_id
            LEFT JOIN time_slots current_slot ON current_slot.slot_id = scr.current_slot_id
            LEFT JOIN time_slots requested_slot ON requested_slot.slot_id = scr.requested_slot_id
            WHERE f.user_id = %s
            ORDER BY scr.created_at DESC, scr.ticket_id DESC
            LIMIT 100
        """, (session["user_id"],))
        rows = cur.fetchall()
        for row in rows:
            for key in ("created_at", "reviewed_at"):
                if row.get(key) is not None:
                    row[key] = str(row[key])
        return jsonify({"tickets": rows})
    except Exception as exc:
        current_app.logger.exception("Could not load faculty schedule-change tickets")
        return jsonify({"error": db_error_message(exc)}), 500
    finally:
        cur.close()
        conn.close()


@bp.get("/api/faculty/my-schedule")
@login_required
def faculty_my_schedule():
    if session.get("role") != "FACULTY":
        return jsonify({"error": "Faculty access required."}), 403

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    try:
        # Identify the logged-in faculty member.
        cur.execute("""
            SELECT faculty_id
            FROM faculty
            WHERE user_id = %s
        """, (session["user_id"],))

        faculty = cur.fetchone()

        if not faculty:
            return jsonify({"error": "Faculty profile not found."}), 404

        faculty_id = faculty["faculty_id"]

        # Fetch the currently active regular timetable.
        cur.execute("""
            SELECT
                te.entry_id,
                te.day_of_week,
                te.slot_id,
                ts.slot_label,
                ts.start_time,
                ts.end_time,
                COALESCE(
                    te.activity_name,
                    s.subject_name,
                    te.activity_type
                ) AS activity_name,
                te.activity_type,
                c.room_code
            FROM timetable_entries te
            JOIN time_slots ts
                ON ts.slot_id = te.slot_id
            JOIN timetables t
                ON t.timetable_id = te.timetable_id
            LEFT JOIN subjects s
                ON s.subject_id = te.subject_id
            LEFT JOIN classrooms c
                ON c.classroom_id = te.classroom_id
            WHERE te.faculty_id = %s
              AND t.status = 'ACTIVE'
              AND t.effective_from <= CURDATE()
              AND (
                  t.effective_to IS NULL
                  OR t.effective_to >= CURDATE()
              )
            ORDER BY
                FIELD(
                    te.day_of_week,
                    'MONDAY', 'TUESDAY', 'WEDNESDAY',
                    'THURSDAY', 'FRIDAY', 'SATURDAY'
                ),
                ts.slot_order
        """, (faculty_id,))

        regular_entries = cur.fetchall()

        # Fetch confirmed bookings occurring in the current week.
        # Future weeks will appear automatically when they become current.
        cur.execute("""
            SELECT
                b.booking_id,
                b.booking_date,
                b.slot_id,
                ts.slot_label,
                ts.start_time,
                ts.end_time,
                br.booking_type,
                COALESCE(
                    br.reason,
                    'Classroom booking'
                ) AS activity_name,
                c.room_code
            FROM bookings b
            JOIN booking_requests br
                ON br.request_id = b.request_id
            JOIN time_slots ts
                ON ts.slot_id = b.slot_id
            JOIN classrooms c
                ON c.classroom_id = b.classroom_id
            WHERE b.faculty_id = %s
              AND b.status = 'CONFIRMED'
              AND br.status = 'APPROVED'
              AND b.booking_date BETWEEN
                DATE_ADD(
                    CURDATE(),
                    INTERVAL (
                        CASE
                            WHEN WEEKDAY(CURDATE()) = 6 THEN 1
                            ELSE -WEEKDAY(CURDATE())
                        END
                    ) DAY
                )
                AND DATE_ADD(
                    DATE_ADD(
                        CURDATE(),
                        INTERVAL (
                            CASE
                                WHEN WEEKDAY(CURDATE()) = 6 THEN 1
                                ELSE -WEEKDAY(CURDATE())
                            END
                        ) DAY
                    ),
                    INTERVAL 5 DAY
                )
              AND (
                  b.booking_date > CURDATE()
                  OR (
                      b.booking_date = CURDATE()
                      AND ts.end_time > CURTIME()
                  )
              )
            ORDER BY b.booking_date, ts.slot_order
        """, (faculty_id,))

        bookings = cur.fetchall()

        # Fetch timetable columns.
        cur.execute("""
            SELECT
                slot_id,
                slot_label,
                start_time,
                end_time,
                slot_order
            FROM time_slots
            ORDER BY slot_order
        """)

        slots = cur.fetchall()

        # Serialize MySQL TIME values.
        for collection in (slots, regular_entries, bookings):
            for item in collection:
                for field in ("start_time", "end_time"):
                    if field in item:
                        item[field] = serialize_time(item[field])

        # Serialize booking dates consistently.
        for booking in bookings:
            booking_date = booking.get("booking_date")

            if booking_date is not None:
                booking["booking_date"] = (
                    booking_date.strftime("%Y-%m-%d")
                    if hasattr(booking_date, "strftime")
                    else str(booking_date)[:10]
                )

        return jsonify({
            "success": True,
            "slots": slots,
            "regular_entries": regular_entries,
            "bookings": bookings
        })

    except Exception:
        current_app.logger.exception("Failed to load faculty schedule")

        return jsonify({
            "success": False,
            "error": "Unable to load your schedule."
        }), 500

    finally:
        cur.close()
        conn.close()

