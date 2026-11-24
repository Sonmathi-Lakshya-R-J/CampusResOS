from datetime import date
from flask import Blueprint, current_app, jsonify, request, session

from db import get_connection
from services.booking_helpers import (
    booking_time_error,
    faculty_schedule_conflict,
    room_has_schedule_conflict,
    db_error_message,
    login_required,
)

bp = Blueprint("bookings", __name__)


def get_booking_priority(purpose):
    """Return the server-assigned priority for a booking purpose."""
    normalized = purpose.strip().casefold()

    priorities = {
        "placement meeting": 1,
        "pre-placement talks": 1,
        "syllabus completion": 2,
        "additional lecture": 3,
        "workshop / seminar": 3,
        "faculty meeting": 3,
        "club events": 4,
    }

    return priorities.get(normalized, 5)


def is_valid_booking_purpose(purpose):
    allowed = {
        "Placement meeting",
        "Pre-placement talks",
        "Syllabus completion",
        "Additional lecture",
        "Workshop / Seminar",
        "Faculty meeting",
        "Club events",
    }

    if purpose in allowed:
        return True

    if purpose.startswith("Others: "):
        description = purpose[len("Others: "):].strip()
        return bool(description) and len(description) <= 240

    return False




@bp.get("/api/bookings")
@login_required
def list_bookings():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    try:
        query = """
            SELECT
                b.booking_id,
                b.classroom_id,
                b.booking_date,
                b.slot_id,
                ts.start_time,
                ts.end_time,
                ts.slot_label,
                br.reason AS purpose,
                b.status,
                c.room_code,
                c.room_name,
                u.full_name AS requester
            FROM bookings b
            JOIN time_slots ts
                ON ts.slot_id = b.slot_id
            JOIN classrooms c
                ON c.classroom_id = b.classroom_id
            JOIN faculty f
                ON f.faculty_id = b.faculty_id
            JOIN users u
                ON u.user_id = f.user_id
            JOIN booking_requests br
                ON br.request_id = b.request_id
        """

        params = ()

        if session["role"] != "ADMIN":
            query += " WHERE u.user_id = %s"
            params = (session["user_id"],)

        query += """
            ORDER BY b.booking_id DESC
        """

        cur.execute(query, params)
        rows = cur.fetchall()

        for row in rows:
            for key in ("booking_date", "start_time", "end_time"):
                if row.get(key) is not None:
                    row[key] = str(row[key])

        return jsonify({"bookings": rows})

    finally:
        cur.close()
        conn.close()


@bp.post("/api/recurring/availability")
@login_required
def recurring_availability():
    if session.get("role") != "FACULTY":
        return jsonify({"error": "Only faculty can check availability."}), 403

    payload = request.get_json(silent=True) or {}

    try:
        slot_id = int(payload.get("slot_id"))
        dates = sorted(set(
            date.fromisoformat(str(d))
            for d in payload.get("dates", [])
        ))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid slot or booking dates."}), 400

    if not dates:
        return jsonify({"error": "No booking dates were provided."}), 400

    if len(dates) > 60:
        return jsonify({"error": "A maximum of 60 occurrences is allowed."}), 400

    if any(d < date.today() for d in dates):
        return jsonify({"error": "Past booking dates are not allowed."}), 400

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            "SELECT slot_id, slot_label, start_time, end_time "
            "FROM time_slots WHERE slot_id = %s",
            (slot_id,)
        )
        slot = cur.fetchone()

        if not slot:
            return jsonify({"error": "Invalid time slot."}), 400

        for occurrence in dates:
            time_error = booking_time_error(occurrence, slot["start_time"])
            if time_error:
                return jsonify({
                    "error": f"{occurrence.isoformat()}: {time_error}"
                }), 400


        cur.execute(
            "SELECT faculty_id FROM faculty WHERE user_id = %s",
            (session["user_id"],)
        )
        faculty = cur.fetchone()

        if not faculty:
            return jsonify({"error": "Faculty record not found."}), 403

        for occurrence in dates:
            conflict_message = faculty_schedule_conflict(
                cur, faculty["faculty_id"], occurrence, slot
            )

            if conflict_message:
                return jsonify({
                    "error": f"{occurrence.isoformat()}: {conflict_message}"
                }), 409


            
       

        cur.execute("""
            SELECT classroom_id, room_code, room_name, capacity, room_type
            FROM classrooms
            WHERE status = 'AVAILABLE'
            ORDER BY room_code
        """)

        all_rooms = cur.fetchall()
        available_rooms = []

        for room in all_rooms:
            available_dates = []
            unavailable_dates = []

            for booking_date in dates:
                blocked = room_has_schedule_conflict(
                    cur, room["classroom_id"], booking_date, slot
                )

                if blocked:
                    unavailable_dates.append({
                        "date": booking_date.isoformat(),
                        "reason": "Occupied by a regular class or confirmed booking"
                    })
                else:
                    available_dates.append(booking_date.isoformat())

            if available_dates:
                available_rooms.append({
                    "classroom_id": room["classroom_id"],
                    "room_code": room["room_code"],
                    "room_name": room["room_name"],
                    "capacity": room["capacity"],
                    "room_type": room.get("room_type"),
                    "available_dates": available_dates,
                    "unavailable_dates": unavailable_dates
                })

        # Provide a date-by-date summary across all rooms.
        occurrences = []

        for booking_date in dates:
            rooms_available = [
                room["room_code"]
                for room in available_rooms
                if booking_date.isoformat() in room["available_dates"]
            ]

            occurrences.append({
                "date": booking_date.isoformat(),
                "available": bool(rooms_available),
                "available_rooms": rooms_available,
                "reason": (
                    None if rooms_available
                    else "No classrooms available for this slot"
                )
            })

        return jsonify({
            "ok": True,
            "slot": {
                "slot_id": slot["slot_id"],
                "slot_label": slot["slot_label"],
                "start_time": str(slot["start_time"]),
                "end_time": str(slot["end_time"])
            },
            "dates": [d.isoformat() for d in dates],
            "rooms": available_rooms,
            "occurrences": occurrences
        })

    except Exception as exc:
        current_app.logger.exception("Recurring availability check failed")
        return jsonify({"error": db_error_message(exc)}), 500

    finally:
        cur.close()
        conn.close()


@bp.post("/api/recurring/bookings")
@login_required
def create_recurring_bookings():
    if session.get("role") != "FACULTY":
        return jsonify({"error": "Only faculty can create bookings."}), 403

    payload = request.get_json(silent=True) or {}

    try:
        room_id = int(payload.get("classroom_id"))
        slot_id = int(payload.get("slot_id"))
        dates = sorted(set(
            date.fromisoformat(str(d))
            for d in payload.get("dates", [])
        ))
    except (ValueError, TypeError):
        return jsonify({
            "error": "Invalid classroom, slot, or booking dates."
        }), 400

    purpose = str(payload.get("purpose", "")).strip()

    if not is_valid_booking_purpose(purpose):
        return jsonify({
            "error": "Select a valid purpose. If Others, provide an explanation."
        }), 400

    if not dates:
        return jsonify({"error": "No booking dates were provided."}), 400

    if len(dates) > 60:
        return jsonify({"error": "A maximum of 60 occurrences is allowed."}), 400

    if any(d < date.today() for d in dates):
        return jsonify({"error": "Past booking dates are not allowed."}), 400

    if not purpose or len(purpose) > 255:
        return jsonify({
            "error": "Purpose is required and must not exceed 255 characters."
        }), 400

    if payload.get("confirm") is not True:
        return jsonify({
            "error": "Explicit confirmation is required before creating bookings."
        }), 400

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    acquired_locks = []

    try:
        # Resolve the logged-in faculty member.
        cur.execute(
            "SELECT faculty_id FROM faculty WHERE user_id = %s",
            (session["user_id"],)
        )
        faculty = cur.fetchone()

        if not faculty:
            return jsonify({
                "error": "Your account is not linked to a faculty record."
            }), 403

        faculty_id = faculty["faculty_id"]

        # Validate classroom and slot.
        cur.execute("""
            SELECT classroom_id, capacity
            FROM classrooms
            WHERE classroom_id = %s
              AND status = 'AVAILABLE'
        """, (room_id,))
        room = cur.fetchone()

        if not room:
            return jsonify({
                "error": "Classroom not found or unavailable."
            }), 404

        cur.execute(
            """
            SELECT slot_id, slot_label, start_time, end_time
            FROM time_slots
            WHERE slot_id = %s
            """,
            (slot_id,)
        )
        slot = cur.fetchone()

        if not slot:
            return jsonify({"error": "Invalid time slot."}), 400

        for occurrence in dates:
            time_error = booking_time_error(occurrence, slot["start_time"])
            if time_error:
                return jsonify({
                    "error": f"{occurrence.isoformat()}: {time_error}"
                }), 400



# Check the faculty member's schedule for every occurrence.
        for occurrence in dates:
            conflict_message = faculty_schedule_conflict(
                cur, faculty_id, occurrence, slot
            )

            if conflict_message:
                return jsonify({
                    "error": f"{occurrence.isoformat()}: {conflict_message}"
                }), 409


    
        # Acquire locks in date order to reduce concurrent booking races.
        for booking_date in dates:
            lock_name = f"cr:{room_id}:{booking_date.isoformat()}"

            cur.execute(
                "SELECT GET_LOCK(%s, 5) AS acquired",
                (lock_name,)
            )
            result = cur.fetchone()

            if not result or result["acquired"] != 1:
                conn.rollback()
                return jsonify({
                    "error": (
                        f"Could not reserve the room lock for "
                        f"{booking_date.isoformat()}. Please retry."
                    )
                }), 409

            acquired_locks.append(lock_name)

        conn.rollback()
        conn.start_transaction()

        # Recheck all dates after acquiring locks.
        # Nothing is inserted until every requested date is checked.
        unavailable_dates = []

        # for booking_date in dates:
        #     cur.execute("""
        #         SELECT booking_id
        #         FROM bookings
        #         WHERE classroom_id = %s
        #           AND booking_date = %s
        #           AND slot_id = %s
        #           AND status = 'CONFIRMED'
        #         LIMIT 1
        #         FOR UPDATE
        #     """, (room_id, booking_date, slot_id))

        #     if cur.fetchone():
        #         unavailable_dates.append({
        #             "date": booking_date.isoformat(),
        #             "reason": "Already booked"
        #         })


        if room_has_schedule_conflict(
            cur, room_id, booking_date, slot
        ):
            unavailable_dates.append({
                "date": booking_date.isoformat(),
                "reason": "Occupied by a regular class or confirmed booking"
            })




        if unavailable_dates:
            conn.rollback()
            return jsonify({
                "ok": False,
                "error": "Some dates are no longer available.",
                "unavailable_dates": unavailable_dates,
                "message": (
                    "Run the availability check again and confirm "
                    "which available dates you want to book."
                )
            }), 409

        # Create one request and one booking for every occurrence.
        created = []

        for booking_date in dates:
            cur.execute("""
                INSERT INTO booking_requests (
                    faculty_id,
                    requested_classroom_id,
                    requested_date,
                    slot_id,
                    required_capacity,
                    priority,
                    booking_type,
                    status,
                    reason
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                faculty_id,
                room_id,
                booking_date,
                slot_id,
                room["capacity"],
                get_booking_priority(purpose),
                "PERMANENT",
                "APPROVED",
                purpose
            ))

            request_id = cur.lastrowid

            cur.execute("""
                INSERT INTO bookings (
                    request_id,
                    classroom_id,
                    faculty_id,
                    booking_date,
                    slot_id,
                    status,
                    created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                request_id,
                room_id,
                faculty_id,
                booking_date,
                slot_id,
                "CONFIRMED",
                session["user_id"]
            ))

            booking_id = cur.lastrowid

            cur.execute("""
                INSERT INTO booking_history (
                    booking_id,
                    action,
                    performed_by,
                    notes
                )
                VALUES (%s, %s, %s, %s)
            """, (
                booking_id,
                "CREATED",
                session["user_id"],
                f"Recurring booking: {purpose}"
            ))

            created.append({
                "booking_id": booking_id,
                "request_id": request_id,
                "date": booking_date.isoformat(),
                "status": "CONFIRMED"
            })

        conn.commit()

        return jsonify({
            "ok": True,
            "message": f"{len(created)} bookings created successfully.",
            "slot_label": slot["slot_label"],
            "room_id": room_id,
            "bookings": created
        }), 201

    except Exception as exc:
        conn.rollback()
        current_app.logger.exception("Recurring booking creation failed")
        return jsonify({"error": db_error_message(exc)}), 500

    finally:
        # Release every acquired MySQL named lock.
        for lock_name in reversed(acquired_locks):
            try:
                cur.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))
                cur.fetchone()
            except Exception:
                current_app.logger.exception("Failed to release booking lock")

        cur.close()
        conn.close()


@bp.post("/api/bookings")
@login_required
def create_booking():
    payload = request.get_json(silent=True) or {}

    try:
        room_id = int(payload.get("classroom_id"))
        slot_id = int(payload.get("slot_id"))
        booking_date = date.fromisoformat(
            payload.get("booking_date", "")
        )
        purpose = str(payload.get("purpose", "")).strip()
    except (ValueError, TypeError):
        return jsonify({
            "error": "Invalid classroom, slot, date, or purpose."
        }), 400

    if not is_valid_booking_purpose(purpose) or len(purpose) > 255:
        return jsonify({
            "error": "Select a valid purpose. If Others, provide an explanation."
        }), 400

    if booking_date < date.today():
        return jsonify({
            "error": "Bookings cannot be made for a past date."
        }), 400

    if not purpose or len(purpose) > 255:
        return jsonify({
            "error": "Purpose is required (maximum 255 characters)."
        }), 400

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    lock_name = f"cr:{room_id}:{booking_date.isoformat()}"
    got_lock = False

    try:
        # Booking creation is a faculty-only operation. Admins manage requests
        # and analytics, but do not create bookings from the admin dashboard.
        if session.get("role") != "FACULTY":
            return jsonify({"error": "Only faculty can create bookings."}), 403

        cur.execute("""
            SELECT faculty_id
            FROM faculty
            WHERE user_id = %s
        """, (session["user_id"],))
        faculty = cur.fetchone()
        if not faculty:
            return jsonify({"error": "Your account is not linked to a faculty record."}), 403
        faculty_id = faculty["faculty_id"]

        # Validate classroom.
        cur.execute("""
            SELECT classroom_id, capacity
            FROM classrooms
            WHERE classroom_id = %s
              AND status = 'AVAILABLE'
        """, (room_id,))

        room = cur.fetchone()

        if not room:
            return jsonify({
                "error": "Room not found or unavailable."
            }), 404

        # Validate the predefined time slot.
        cur.execute("""
            SELECT slot_id, start_time, end_time, slot_label
            FROM time_slots
            WHERE slot_id = %s
        """, (slot_id,))

        slot = cur.fetchone()

        if not slot:
            return jsonify({
                "error": "Invalid time slot."
            }), 400

        time_error = booking_time_error(booking_date, slot["start_time"])
        if time_error:
            return jsonify({"error": time_error}), 400



        conflict_message = faculty_schedule_conflict(
            cur, faculty_id, booking_date, slot
        )

        if conflict_message:
            return jsonify({"error": conflict_message}), 409



        # Serialize booking operations for this room and date.
        cur.execute(
            "SELECT GET_LOCK(%s, 5) AS acquired",
            (lock_name,)
        )

        got_lock = (
            (cur.fetchone() or {}).get("acquired") == 1
        )

        if not got_lock:
            return jsonify({
                "error": "Room is busy. Please try again."
            }), 409

        # Start a clean transaction.
        conn.rollback()
        conn.start_transaction()

        # Check confirmed bookings for the selected slot.
        # cur.execute("""
        #     SELECT booking_id
        #     FROM bookings
        #     WHERE classroom_id = %s
        #       AND booking_date = %s
        #       AND slot_id = %s
        #       AND status = 'CONFIRMED'
        #     LIMIT 1
        #     FOR UPDATE
        # """, (room_id, booking_date, slot_id))

        # if cur.fetchone():
        #     conn.rollback()
        #     return jsonify({
        #         "error": "This room is already booked for that time slot."
        #     }), 409



        if room_has_schedule_conflict(
            cur, room_id, booking_date, slot
        ):
            conn.rollback()
            return jsonify({
                "error": "This classroom is occupied by a regular class or another confirmed booking."
            }), 409





        # First request only checks availability.
        if payload.get("confirm") is not True:
            conn.rollback()

            return jsonify({
                "ok": True,
                "available": True,
                "needs_confirmation": True,
                "slot_label": slot["slot_label"],
                "message": (
                    "Room is available. Confirm to finalize the booking."
                )
            })

        # Create the approved request using the current schema.
        cur.execute("""
            INSERT INTO booking_requests (
                faculty_id,
                requested_classroom_id,
                requested_date,
                slot_id,
                required_capacity,
                priority,
                booking_type,
                status,
                reason
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            faculty_id,
            room_id,
            booking_date,
            slot_id,
            1,
            get_booking_priority(purpose),
            "TEMPORARY",
            "APPROVED",
            purpose
        ))

        request_id = cur.lastrowid

        # Create the confirmed booking using slot_id.
        cur.execute("""
            INSERT INTO bookings (
                request_id,
                classroom_id,
                faculty_id,
                booking_date,
                slot_id,
                status,
                created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            request_id,
            room_id,
            faculty_id,
            booking_date,
            slot_id,
            "CONFIRMED",
            session["user_id"]
        ))

        booking_id = cur.lastrowid

        # Record the action in booking history.
        cur.execute("""
            INSERT INTO booking_history (
                booking_id,
                action,
                performed_by,
                notes
            )
            VALUES (%s, %s, %s, %s)
        """, (
            booking_id,
            "CREATED",
            session["user_id"],
            purpose
        ))

        conn.commit()

        return jsonify({
            "ok": True,
            "booking_id": booking_id,
            "request_id": request_id,
            "slot_id": slot_id,
            "slot_label": slot["slot_label"],
            "status": "CONFIRMED"
        }), 201

    except Exception as exc:
        conn.rollback()
        current_app.logger.exception("Booking creation failed")

        return jsonify({
            "error": db_error_message(exc)
        }), 500

    finally:
        if got_lock:
            try:
                cur.execute(
                    "SELECT RELEASE_LOCK(%s)",
                    (lock_name,)
                )
                cur.fetchone()
            except Exception:
                current_app.logger.exception(
                    "Failed to release booking lock"
                )

        cur.close()
        conn.close()
