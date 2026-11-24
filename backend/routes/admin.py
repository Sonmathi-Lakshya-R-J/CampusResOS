from flask import Blueprint, current_app, jsonify, request, session

from db import get_connection
from services.booking_helpers import (
    db_error_message,
    login_required,
    admin_required,
)

bp = Blueprint("admin", __name__)


@bp.get("/api/admin/regular-classes")
@login_required
def admin_regular_classes():
    if session.get("role") != "ADMIN":
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    try:
        query = """
            SELECT
                te.entry_id,
                te.classroom_id,
                te.day_of_week,
                te.slot_id,
                te.activity_name,
                te.activity_type,
                te.notes
            FROM timetable_entries te
            WHERE te.classroom_id IS NOT NULL
            ORDER BY te.day_of_week, te.slot_id
        """

        cur.execute(query)
        rows = cur.fetchall()

        return jsonify({"regular_entries": rows})

    finally:
        cur.close()
        conn.close()


@bp.get("/api/admin/requests")
@admin_required
def admin_requests():
    """Return only unresolved regular-timetable change tickets for the admin queue."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT
                scr.ticket_id,
                scr.ticket_id AS request_id,
                scr.faculty_id,
                scr.timetable_entry_id,
                scr.current_day,
                scr.current_slot_id,
                current_slot.slot_label AS current_slot_label,
                current_slot.start_time AS current_start_time,
                current_slot.end_time AS current_end_time,
                scr.requested_day,
                scr.requested_slot_id,
                requested_slot.slot_label AS requested_slot_label,
                requested_slot.start_time AS requested_start_time,
                requested_slot.end_time AS requested_end_time,
                scr.requested_classroom_id,
                room.room_code,
                room.room_name,
                scr.reason AS purpose,
                scr.reason,
                scr.status,
                scr.created_at,
                u.full_name AS requester
            FROM schedule_change_requests scr
            JOIN faculty f ON f.faculty_id = scr.faculty_id
            JOIN users u ON u.user_id = f.user_id
            LEFT JOIN time_slots current_slot
                ON current_slot.slot_id = scr.current_slot_id
            LEFT JOIN time_slots requested_slot
                ON requested_slot.slot_id = scr.requested_slot_id
            LEFT JOIN classrooms room
                ON room.classroom_id = scr.requested_classroom_id
            WHERE scr.status = 'PENDING'
            ORDER BY scr.created_at ASC, scr.ticket_id ASC
            LIMIT 100
        """)
        rows = cur.fetchall()
        for row in rows:
            for key in (
                "current_start_time", "current_end_time",
                "requested_start_time", "requested_end_time", "created_at"
            ):
                if row.get(key) is not None:
                    row[key] = str(row[key])
        return jsonify({"requests": rows, "tickets": rows})
    except Exception as exc:
        current_app.logger.exception("Could not load pending schedule-change tickets")
        return jsonify({"error": db_error_message(exc)}), 500
    finally:
        cur.close()
        conn.close()


@bp.get("/api/admin/schedule-change-requests/history")
@admin_required
def admin_schedule_change_history():
    """Return reviewed schedule-change tickets without deleting their history."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT
                scr.ticket_id,
                scr.faculty_id,
                u.full_name AS requester,
                scr.current_day,
                current_slot.slot_label AS current_slot_label,
                scr.requested_day,
                requested_slot.slot_label AS requested_slot_label,
                room.room_code,
                scr.reason,
                scr.status,
                scr.review_note,
                reviewer.full_name AS reviewed_by_name,
                scr.created_at,
                scr.reviewed_at
            FROM schedule_change_requests scr
            JOIN faculty f ON f.faculty_id = scr.faculty_id
            JOIN users u ON u.user_id = f.user_id
            LEFT JOIN time_slots current_slot
                ON current_slot.slot_id = scr.current_slot_id
            LEFT JOIN time_slots requested_slot
                ON requested_slot.slot_id = scr.requested_slot_id
            LEFT JOIN classrooms room
                ON room.classroom_id = scr.requested_classroom_id
            LEFT JOIN users reviewer
                ON reviewer.user_id = scr.reviewed_by
            WHERE scr.status IN ('APPROVED', 'REJECTED')
            ORDER BY scr.reviewed_at DESC, scr.ticket_id DESC
            LIMIT 200
        """)
        rows = cur.fetchall()
        for row in rows:
            for key in ("created_at", "reviewed_at"):
                if row.get(key) is not None:
                    row[key] = str(row[key])
        return jsonify({"history": rows})
    except Exception as exc:
        current_app.logger.exception("Could not load schedule-change history")
        return jsonify({"error": db_error_message(exc)}), 500
    finally:
        cur.close()
        conn.close()


@bp.post("/api/admin/schedule-change-requests/<int:ticket_id>/decision")
@admin_required
def decide_schedule_change_request(ticket_id):
    """Review a ticket and atomically apply conflict-free timetable changes."""
    payload = request.get_json(silent=True) or {}
    decision = str(payload.get("decision", "")).strip().upper()
    note = str(payload.get("note", "")).strip()[:500]

    if decision not in ("APPROVED", "REJECTED"):
        return jsonify({"error": "Decision must be APPROVED or REJECTED."}), 400

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        conn.start_transaction()

        cur.execute("""
            SELECT * FROM schedule_change_requests
            WHERE ticket_id = %s FOR UPDATE
        """, (ticket_id,))
        ticket = cur.fetchone()
        if not ticket:
            conn.rollback()
            return jsonify({"error": "Schedule-change ticket not found."}), 404
        if ticket["status"] != "PENDING":
            conn.rollback()
            return jsonify({"error": "This ticket has already been reviewed."}), 409

        if decision == "APPROVED":
            if not ticket.get("timetable_entry_id"):
                conn.rollback()
                return jsonify({"error": "This ticket is not linked to a timetable entry."}), 409

            # Lock and validate the exact active timetable entry being changed.
            cur.execute("""
                SELECT te.entry_id, te.timetable_id, te.day_of_week, te.slot_id,
                       te.faculty_id, te.classroom_id, t.section_id
                FROM timetable_entries te
                JOIN timetables t ON t.timetable_id = te.timetable_id
                WHERE te.entry_id = %s
                  AND te.faculty_id = %s
                  AND t.status = 'ACTIVE'
                  AND t.effective_from <= CURDATE()
                  AND (t.effective_to IS NULL OR t.effective_to >= CURDATE())
                FOR UPDATE
            """, (ticket["timetable_entry_id"], ticket["faculty_id"]))
            entry = cur.fetchone()
            if not entry:
                conn.rollback()
                return jsonify({"error": "The original timetable entry is no longer active. Refresh the ticket and try again."}), 409

            day = str(ticket.get("requested_day") or "").upper()
            slot_id = ticket.get("requested_slot_id")
            if day not in {"MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"} or not slot_id:
                conn.rollback()
                return jsonify({"error": "The ticket has an invalid requested day or time slot."}), 400

            cur.execute("SELECT slot_id, start_time, end_time FROM time_slots WHERE slot_id = %s", (slot_id,))
            requested_slot = cur.fetchone()
            if not requested_slot:
                conn.rollback()
                return jsonify({"error": "The requested time slot no longer exists."}), 400

            # If no room was requested, retain the entry's current classroom.
            classroom_id = ticket.get("requested_classroom_id") or entry.get("classroom_id")
            if classroom_id is not None:
                cur.execute(
                    """
                    SELECT classroom_id
                    FROM classrooms
                    WHERE classroom_id = %s
                    AND status = 'AVAILABLE'
                    """,
                    (classroom_id,)
                )
                if not cur.fetchone():
                    conn.rollback()
                    return jsonify({"error": "The requested classroom is inactive or does not exist."}), 409

            # Any time overlap counts, not only identical slot IDs.
            conflict_checks = [
                ("Faculty conflict", """
                    SELECT te.entry_id
                    FROM timetable_entries te
                    JOIN timetables t ON t.timetable_id = te.timetable_id
                    JOIN time_slots ts ON ts.slot_id = te.slot_id
                    WHERE te.entry_id <> %s AND te.faculty_id = %s
                      AND te.day_of_week = %s
                      AND t.status = 'ACTIVE'
                      AND t.effective_from <= CURDATE()
                      AND (t.effective_to IS NULL OR t.effective_to >= CURDATE())
                      AND ts.start_time < %s AND ts.end_time > %s
                    LIMIT 1
                """, (entry["entry_id"], ticket["faculty_id"], day, requested_slot["end_time"], requested_slot["start_time"])),
                ("Section/class conflict", """
                    SELECT te.entry_id
                    FROM timetable_entries te
                    JOIN timetables t ON t.timetable_id = te.timetable_id
                    JOIN time_slots ts ON ts.slot_id = te.slot_id
                    WHERE te.entry_id <> %s AND t.section_id = %s
                      AND te.day_of_week = %s
                      AND t.status = 'ACTIVE'
                      AND t.effective_from <= CURDATE()
                      AND (t.effective_to IS NULL OR t.effective_to >= CURDATE())
                      AND ts.start_time < %s AND ts.end_time > %s
                    LIMIT 1
                """, (entry["entry_id"], entry["section_id"], day, requested_slot["end_time"], requested_slot["start_time"])),
            ]
            if classroom_id is not None:
                conflict_checks.append(("Classroom conflict", """
                    SELECT te.entry_id
                    FROM timetable_entries te
                    JOIN timetables t ON t.timetable_id = te.timetable_id
                    JOIN time_slots ts ON ts.slot_id = te.slot_id
                    WHERE te.entry_id <> %s AND te.classroom_id = %s
                      AND te.day_of_week = %s
                      AND t.status = 'ACTIVE'
                      AND t.effective_from <= CURDATE()
                      AND (t.effective_to IS NULL OR t.effective_to >= CURDATE())
                      AND ts.start_time < %s AND ts.end_time > %s
                    LIMIT 1
                """, (entry["entry_id"], classroom_id, day, requested_slot["end_time"], requested_slot["start_time"])))

            conflicts = []
            for label, sql, params in conflict_checks:
                cur.execute(sql, params)
                if cur.fetchone():
                    conflicts.append(label)
            if conflicts:
                conn.rollback()
                return jsonify({
                    "error": "Approval blocked. Resolve these conflicts first: " + ", ".join(conflicts) + ".",
                    "conflicts": conflicts,
                    "status": "PENDING"
                }), 409

            # Apply the timetable change and ticket decision in the same transaction.
            cur.execute("""
                UPDATE timetable_entries
                SET day_of_week = %s, slot_id = %s, classroom_id = %s
                WHERE entry_id = %s
            """, (day, slot_id, classroom_id, entry["entry_id"]))

        cur.execute("""
            UPDATE schedule_change_requests
            SET status = %s, reviewed_by = %s, review_note = %s,
                reviewed_at = CURRENT_TIMESTAMP
            WHERE ticket_id = %s AND status = 'PENDING'
        """, (decision, session["user_id"], note or None, ticket_id))
        if cur.rowcount != 1:
            conn.rollback()
            return jsonify({"error": "Ticket status changed while processing. Refresh and try again."}), 409

        conn.commit()
        return jsonify({
            "ok": True,
            "ticket_id": ticket_id,
            "status": decision,
            "timetable_updated": decision == "APPROVED",
            "message": "Ticket approved and timetable updated." if decision == "APPROVED" else "Schedule-change ticket rejected."
        })
    except Exception as exc:
        conn.rollback()
        current_app.logger.exception("Could not process schedule-change ticket")
        return jsonify({"error": db_error_message(exc)}), 500
    finally:
        cur.close()
        conn.close()

