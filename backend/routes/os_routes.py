import re
from datetime import timedelta

from flask import Blueprint, jsonify, request

from db import get_connection
from os_client import worker_command, worker_status
from services.booking_helpers import db_error_message, login_required

bp = Blueprint("os_routes", __name__)


@bp.get("/api/os/status")
@login_required
def os_status():
    return jsonify(worker_status())


@bp.get("/api/os/schedule")
@login_required
def os_schedule():
    algorithm = request.args.get("algorithm", "FCFS").upper()

    if algorithm not in ("FCFS", "SJF", "PRIORITY"):
        return jsonify({
            "error": "Algorithm must be FCFS, SJF or PRIORITY."
        }), 400

    # Fetch real pending booking requests.
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        try:
            cur.execute("""
                SELECT
                    br.request_id,
                    br.priority,
                    br.created_at,
                    ts.start_time,
                    ts.end_time,
                    GREATEST(
                        1,
                        CEIL(
                            TIME_TO_SEC(
                                TIMEDIFF(ts.end_time, ts.start_time)
                            ) / 60
                        )
                    ) AS burst_minutes
                FROM booking_requests br
                LEFT JOIN time_slots ts
                    ON ts.slot_id = br.slot_id
                WHERE br.status = 'PENDING'
                ORDER BY br.created_at ASC, br.request_id ASC
                LIMIT 64
            """)

            rows = cur.fetchall()

        finally:
            cur.close()
            conn.close()

    except Exception as exc:
        return jsonify({
            "error": db_error_message(exc)
        }), 500

    if not rows:
        return jsonify({
            "algorithm": algorithm,
            "jobs": 0,
            "message": "No pending booking requests to schedule.",
            "results": []
        })

    # Convert request creation times into simulated arrival times.
    earliest_created = rows[0]["created_at"]

    jobs = []
    request_map = {}

    for index, row in enumerate(rows, start=1):
        request_id = int(row["request_id"])
        created_at = row["created_at"]

        if created_at is None:
            arrival = index - 1
        else:
            arrival = max(
                0,
                int((created_at - earliest_created).total_seconds() // 60)
            )

        burst = max(1, int(row["burst_minutes"] or 1))
        priority = (
            3 if row["priority"] is None
            else int(row["priority"])
        )

        jobs.append(f"{arrival},{burst},{priority}")

        request_map[index] = {
            "request_id": request_id,
            "priority": priority,
            "arrival": arrival,
            "burst": burst,
            "created_at": created_at
        }

    command = f"SCHEDULE|{algorithm}|{';'.join(jobs)}"

    # Send the actual booking requests to the C/POSIX worker.
    try:
        reply = worker_command(command)
    except (OSError, AttributeError, TimeoutError) as exc:
        return jsonify({
            "error": (
                "C/POSIX worker unavailable. "
                "Start os_module/campusresos_worker."
            ),
            "details": str(exc)
        }), 503

    if not reply.startswith("OK|"):
        return jsonify({
            "error": "The C/POSIX worker returned an invalid response.",
            "worker_reply": reply
        }), 502

    # Parse each job's scheduling metrics.
    pattern = (
        r"P(\d+)\(start=([\d.]+),finish=([\d.]+),"
        r"wait=([\d.]+),turnaround=([\d.]+)\)"
    )

    matches = re.findall(pattern, reply)

    if len(matches) != len(rows):
        return jsonify({
            "error": "Could not parse all scheduling results.",
            "expected_jobs": len(rows),
            "parsed_jobs": len(matches),
            "worker_reply": reply
        }), 502

    results = []

    for job_number, start, finish, waiting, turnaround in matches:
        job_number = int(job_number)

        if job_number not in request_map:
            return jsonify({
                "error": "Worker returned an unknown job number.",
                "worker_reply": reply
            }), 502

        job = request_map[job_number]

        results.append({
            "request_id": job["request_id"],
            "priority": job["priority"],
            "arrival": job["arrival"],
            "burst": job["burst"],
            "start": int(float(start)),
            "finish": int(float(finish)),
            "waiting": int(float(waiting)),
            "turnaround": int(float(turnaround))
        })

    # Save the scheduling metrics without changing booking requests.
    try:
        conn = get_connection()
        cur = conn.cursor()

        try:
            for result in results:
                job = request_map[
                    next(
                        number
                        for number, item in request_map.items()
                        if item["request_id"] == result["request_id"]
                    )
                ]

                queued_at = job["created_at"] or earliest_created

                simulated_start = (
                    earliest_created
                    + timedelta(minutes=result["start"])
                )

                simulated_finish = (
                    earliest_created
                    + timedelta(minutes=result["finish"])
                )

                cur.execute("""
                    INSERT INTO os_job_metrics (
                        request_id,
                        algorithm,
                        priority_value,
                        arrival_sequence,
                        queued_at,
                        started_at,
                        finished_at,
                        waiting_ms,
                        turnaround_ms,
                        outcome
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    )
                """, (
                    result["request_id"],
                    algorithm,
                    result["priority"],
                    result["arrival"],
                    queued_at,
                    simulated_start,
                    simulated_finish,
                    result["waiting"] * 60000,
                    result["turnaround"] * 60000,
                    "SCHEDULED"
                ))

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            cur.close()
            conn.close()

    except Exception as exc:
        return jsonify({
            "error": "Scheduling completed, but metrics could not be saved.",
            "details": db_error_message(exc),
            "worker_reply": reply
        }), 500

    return jsonify({
        "algorithm": algorithm,
        "jobs": len(results),
        "worker_reply": reply,
        "results": results,
        "metrics_saved": True,
        "booking_statuses_changed": False
    })

