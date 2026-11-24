import os
import sys
from pathlib import Path

from flask import Flask, jsonify, send_from_directory

sys.path.insert(0, str(Path(__file__).resolve().parent))

from os_client import worker_status
from advanced import bp as advanced_bp
from db import get_connection
from services.booking_helpers import db_error_message

from routes.auth import bp as auth_bp
from routes.classrooms import bp as classrooms_bp
from routes.bookings import bp as bookings_bp
from routes.admin import bp as admin_bp
from routes.faculty import bp as faculty_bp
from routes.os_routes import bp as os_routes_bp


BASE = Path(__file__).resolve().parent.parent

app = Flask(__name__, static_folder=None)

app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY environment variable is not set.")

app.register_blueprint(advanced_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(classrooms_bp)
app.register_blueprint(bookings_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(faculty_bp)
app.register_blueprint(os_routes_bp)


@app.get("/")
def index():
    return send_from_directory(BASE / "frontend", "index.html")


@app.get("/<path:path>")
def frontend_files(path):
    candidate = (BASE / "frontend" / path).resolve()
    frontend_root = (BASE / "frontend").resolve()

    if frontend_root not in candidate.parents and candidate != frontend_root:
        return jsonify({"error": "Not found"}), 404

    if candidate.is_file():
        return send_from_directory(BASE / "frontend", path)

    return jsonify({"error": "Not found"}), 404


@app.get("/api/health")
def health():
    try:
        worker = worker_status()
    except (OSError, AttributeError) as exc:
        worker = {
            "available": False,
            "error": str(exc)
        }

    try:
        conn = get_connection()
        conn.ping(reconnect=True, attempts=1, delay=0)
        conn.close()
        db_status = "ok"

    except Exception as exc:
        db_status = "unavailable"
        return jsonify({
            "status": "degraded",
            "database": db_status,
            "worker": worker,
            "error": db_error_message(exc)
        }), 503

    return jsonify({
        "status": "ok" if worker["available"] else "degraded",
        "database": db_status,
        "worker": worker
    })


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG") == "1"
    )
