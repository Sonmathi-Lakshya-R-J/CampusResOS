from flask import Flask, request, jsonify
import subprocess
import json
import os

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
C_SOURCE = os.path.join(BASE_DIR, "c_module.c")
C_PROGRAM = os.path.join(BASE_DIR, "c_module")


def compile_c_module():
    result = subprocess.run(
        ["cc", "-pthread", C_SOURCE, "-o", C_PROGRAM],
        capture_output=True,
        text=True,
        timeout=30
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "C compilation failed")


def send_to_c_module(algorithm, bookings, mode="SAFE"):
    input_data = algorithm + "\n"
    input_data += str(len(bookings)) + "\n"

    for booking in bookings:
        input_data += (
            f"{booking['booking_id']} "
            f"{booking['professor_id']} "
            f"{booking['room']} "
            f"{booking['day']} "
            f"{booking['start_time']} "
            f"{booking['end_time']} "
            f"{booking['students']} "
            f"{booking['priority']} "
            f"{booking['processing_time']} "
            f"{booking['booking_type']}\n"
        )

    environment = os.environ.copy()
    environment["RACE_MODE"] = mode

    try:
        result = subprocess.run(
            [C_PROGRAM],
            input=input_data,
            text=True,
            capture_output=True,
            timeout=5,
            env=environment
        )

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "C module timed out"}

    if result.returncode != 0:
        return {
            "success": False,
            "error": result.stderr.strip() or "C module failed"
        }

    try:
        return json.loads(result.stdout)

    except json.JSONDecodeError:
        return {
            "success": False,
            "error": "Invalid JSON returned by C module",
            "raw_output": result.stdout
        }


@app.route("/")
def home():
    return "CampusResOS Flask + C is working!"


@app.route("/booking", methods=["POST"])
def booking():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "error": "A JSON object is required"
        }), 400

    algorithm = str(data.get("algorithm", "")).upper()
    bookings = data.get("bookings")
    mode = str(data.get("mode", "SAFE")).upper()

    if algorithm not in ("FCFS", "PRIORITY"):
        return jsonify({
            "success": False,
            "error": "Algorithm must be FCFS or PRIORITY"
        }), 400

    if not isinstance(bookings, list) or not bookings:
        return jsonify({
            "success": False,
            "error": "A non-empty bookings list is required"
        }), 400

    if mode not in ("SAFE", "UNSAFE"):
        return jsonify({
            "success": False,
            "error": "Mode must be SAFE or UNSAFE"
        }), 400

    required_fields = (
        "booking_id",
        "professor_id",
        "room",
        "day",
        "start_time",
        "end_time",
        "students",
        "priority",
        "processing_time",
        "booking_type"
    )

    for index, booking_data in enumerate(bookings):
        if not isinstance(booking_data, dict):
            return jsonify({
                "success": False,
                "error": f"Booking {index + 1} must be a JSON object"
            }), 400

        missing = [
            field for field in required_fields
            if field not in booking_data
        ]

        if missing:
            return jsonify({
                "success": False,
                "error": f"Booking {index + 1} is missing: {', '.join(missing)}"
            }), 400

        for field in ("room", "day", "start_time", "end_time", "booking_type"):
            value = str(booking_data[field])

            if not value or any(char.isspace() for char in value):
                return jsonify({
                    "success": False,
                    "error": f"{field} must be a non-empty value without spaces"
                }), 400

        try:
            for field in (
                "booking_id",
                "professor_id",
                "students",
                "priority",
                "processing_time"
            ):
                booking_data[field] = int(booking_data[field])
        except (TypeError, ValueError):
            return jsonify({
                "success": False,
                "error": f"Booking {index + 1} has invalid numeric fields"
            }), 400

    try:
        compile_c_module()
        result = send_to_c_module(algorithm, bookings, mode)

    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        return jsonify({
            "success": False,
            "error": str(error)
        }), 500

    return jsonify(result), 200 if result.get("success") else 500


@app.route("/deadlock", methods=["GET"])
def deadlock():
    return jsonify({
        "success": False,
        "error": "The current C module does not implement a deadlock demonstration yet."
    }), 501


if __name__ == "__main__":
    app.run(debug=False, port=5000)