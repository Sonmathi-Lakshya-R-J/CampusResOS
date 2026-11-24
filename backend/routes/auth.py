from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash

from db import get_connection
from services.booking_helpers import login_required

bp = Blueprint("auth", __name__)


@bp.post("/api/login")
def login():
    payload = request.get_json(silent=True) or {}

    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))

    if not email or not password:
        return jsonify({
            "success": False,
            "error": "Email and password are required."
        }), 400

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute("""
            SELECT user_id, full_name, email,
                   password_hash, role, is_active
            FROM users
            WHERE email = %s
        """, (email,))

        user = cur.fetchone()

        if (
            not user
            or not user["is_active"]
            or not check_password_hash(user["password_hash"], password)
        ):
            return jsonify({
                "success": False,
                "error": "Invalid email or password."
            }), 401

        session.clear()
        session["user_id"] = user["user_id"]
        session["name"] = user["full_name"]
        session["role"] = user["role"]

        return jsonify({
            "success": True,
            "user": {
                "id": user["user_id"],
                "name": user["full_name"],
                "email": user["email"],
                "role": user["role"]
            }
        }), 200

    finally:
        cur.close()
        conn.close()






@bp.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})

@bp.get("/api/me")
@login_required
def me():
    return jsonify({"id": session["user_id"], "name": session["name"], "role": session["role"]})
