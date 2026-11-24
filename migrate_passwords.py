
from backend.db import get_connection
from werkzeug.security import generate_password_hash

conn = get_connection()
cur = conn.cursor(dictionary=True)

try:
    cur.execute("""
        SELECT
            @@hostname AS server,
            @@port AS port,
            CURRENT_USER() AS db_user,
            DATABASE() AS db_name
    """)
    print("Python database connection:", cur.fetchone())

    cur.execute("SELECT COUNT(*) AS total FROM users")
    print("Python user count:", cur.fetchone())
    cur.execute("""
            SELECT user_id, password_hash
            FROM users
        """)

    users = cur.fetchall()

    updated = 0

    for user in users:
        old_password = user["password_hash"]

        # Skip passwords that are already Werkzeug hashes
        if old_password.startswith("scrypt:") or old_password.startswith("pbkdf2:"):
            continue

        new_hash = generate_password_hash(old_password)

        cur.execute("""
            UPDATE users
            SET password_hash = %s
            WHERE user_id = %s
        """, (new_hash, user["user_id"]))

        updated += 1

    conn.commit()
    print(f"Successfully migrated {updated} passwords.")

except Exception:
    conn.rollback()
    raise

finally:
    cur.close()
    conn.close()
