import os
import sys
import json
import hashlib
import hmac
import secrets
import subprocess
import getpass
from datetime import date, datetime, time, timedelta

import mysql.connector
from mysql.connector import Error


DB_CONFIG = {
    "host": os.getenv("CAMPUSRESOS_DB_HOST", "localhost"),
    "user": os.getenv("CAMPUSRESOS_DB_USER", "root"),
    "password": os.getenv("CAMPUSRESOS_DB_PASSWORD", ""),
    "database": os.getenv("CAMPUSRESOS_DB_NAME", "campusresos_new"),
}

C_EXECUTABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "c_module")
ACTIVE_BOOKING_STATUSES = ("CONFIRMED", "COMPLETED")
WEEKDAYS = {
    "1": "Monday",
    "2": "Tuesday",
    "3": "Wednesday",
    "4": "Thursday",
    "5": "Friday",
    "6": "Saturday",
    "7": "Sunday",
}


def connect_db():
    return mysql.connector.connect(**DB_CONFIG)


def fetch_all(sql, params=()):
    connection = connect_db()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def fetch_one(sql, params=()):
    connection = connect_db()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()


def execute_sql(sql, params=()):
    connection = connect_db()
    cursor = connection.cursor()
    try:
        cursor.execute(sql, params)
        connection.commit()
        return cursor.lastrowid
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def password_hash(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        310000,
    ).hex()

    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password, stored_hash):
    if not stored_hash:
        return False

    parts = stored_hash.split("$")

    if len(parts) != 3 or parts[0] != "pbkdf2_sha256":
        return False

    salt = parts[1]
    expected = parts[2]

    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        310000,
    ).hex()

    return hmac.compare_digest(actual, expected)


def pause():
    input("\nPress Enter to continue...")


def line():
    print("-" * 65)


def heading(title):
    print("\n")
    line()
    print(title.center(65))
    line()


def ask_nonempty(prompt):
    while True:
        value = input(prompt).strip()

        if value:
            return value

        print("This field cannot be empty.")


def ask_int(prompt, minimum=None, maximum=None):
    while True:
        value = input(prompt).strip()

        try:
            number = int(value)

            if minimum is not None and number < minimum:
                print(f"Enter a number greater than or equal to {minimum}.")
                continue

            if maximum is not None and number > maximum:
                print(f"Enter a number less than or equal to {maximum}.")
                continue

            return number

        except ValueError:
            print("Enter a valid whole number.")


def ask_date(prompt, allow_past=False):
    while True:
        value = input(prompt).strip()

        try:
            result = date.fromisoformat(value)

            if not allow_past and result < date.today():
                print("Choose today or a future date.")
                continue

            return result

        except ValueError:
            print("Enter the date in YYYY-MM-DD format.")


def ask_time(prompt):
    while True:
        value = input(prompt).strip()

        try:
            result = time.fromisoformat(value)

            if result.second or result.microsecond:
                print("Enter time in HH:MM format.")
                continue

            return result

        except ValueError:
            print("Enter a valid time, such as 09:00 or 14:30.")


def display_table(rows, columns):
    if not rows:
        print("No records found.")
        return

    formatted = []

    for row in rows:
        formatted.append([
            str(row.get(key, "") if row.get(key) is not None else "")
            for key, _ in columns
        ])

    widths = []

    for index, (_, label) in enumerate(columns):
        widths.append(max(
            len(label),
            max(len(row[index]) for row in formatted)
        ))

    header = " | ".join(
        label.ljust(widths[index])
        for index, (_, label) in enumerate(columns)
    )

    print(header)
    print("-+-".join("-" * width for width in widths))

    for row in formatted:
        print(" | ".join(
            value.ljust(widths[index])
            for index, value in enumerate(row)
        ))


def get_user_by_name(full_name, role):
    return fetch_one(
        """
        SELECT u.user_id, u.full_name, u.email, u.password_hash,
               u.role, u.is_active, f.faculty_id
        FROM users u
        LEFT JOIN faculty f ON f.user_id = u.user_id
        WHERE LOWER(u.full_name) = LOWER(%s)
          AND u.role = %s
        """,
        (full_name, role),

    )
def register_user(role):
    role = role.strip().upper()

    if role not in ("ADMIN", "FACULTY"):
        print("Invalid account type.")
        return

    heading(f"CREATE {role} ACCOUNT")

    full_name = ask_nonempty("Full name: ")

    while True:
        password = getpass.getpass("Password: ")

        if len(password) < 8:
            print("Password must contain at least 8 characters.")
            continue

        confirmation = getpass.getpass("Confirm password: ")

        if password != confirmation:
            print("Passwords do not match. Please try again.")
            continue

        break

    department = None
    designation = None

    if role == "FACULTY":
        department = ask_nonempty("Department: ")
        designation = input("Designation: ").strip() or "Faculty"

    connection = connect_db()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO users (full_name, password_hash, role, is_active)
            VALUES (%s, %s, %s, 1)
            """,
            (full_name, password_hash(password), role),
        )

        user_id = cursor.lastrowid

        if role == "FACULTY":
            cursor.execute(
                """
                INSERT INTO faculty (user_id, department, designation)
                VALUES (%s, %s, %s)
                """,
                (user_id, department, designation),
            )

        connection.commit()
        print(f"{role.title()} account created successfully.")

    except Error as error:
        connection.rollback()
        print("Registration failed:", error)

    finally:
        cursor.close()
        connection.close()
def login(role):
    heading(f"LOGIN AS {role}")

    full_name = ask_nonempty("Full name: ")
    password = getpass.getpass("Password: ")

    try:
        user = get_user_by_name(full_name, role)

        if not user or not verify_password(
            password, user["password_hash"]
        ):
            print("Invalid name or password.")
            return None

        if not user["is_active"]:
            print("This account is inactive.")
            return None

        if role == "FACULTY" and not user["faculty_id"]:
            print("Your account does not have a faculty profile.")
            return None

        print(f"\nWelcome, {user['full_name']}!")
        return user

    except Error as error:
        print("Database error:", error)
        return None
def list_classrooms(active_only=False):
    sql = """
        SELECT classroom_id, room_code, room_name, building,
               floor_no, room_type, capacity, status
        FROM classrooms
    """

    if active_only:
        sql += " WHERE status = 'AVAILABLE'"

    sql += " ORDER BY room_code"

    return fetch_all(sql)


def show_classrooms(active_only=False):
    rooms = list_classrooms(active_only)

    display_table(
        rooms,
        [
            ("classroom_id", "ID"),
            ("room_code", "Code"),
            ("room_name", "Name"),
            ("building", "Building"),
            ("floor_no", "Floor"),
            ("room_type", "Type"),
            ("capacity", "Capacity"),
            ("status", "Status"),
        ],
    )

    return rooms


def choose_classroom(active_only=True):
    rooms = show_classrooms(active_only)

    if not rooms:
        return None

    classroom_id = ask_int("Enter classroom ID: ", minimum=1)

    selected = fetch_one(
        """
        SELECT classroom_id, room_code, room_name, building,
               floor_no, room_type, capacity, status
        FROM classrooms
        WHERE classroom_id = %s
        """,
        (classroom_id,),
    )

    if not selected:
        print("Classroom not found.")
        return None

    if active_only and selected["status"] != "AVAILABLE":
        print("This classroom is not currently available for booking.")
        return None

    return selected


def add_classroom():
    heading("ADD CLASSROOM")

    room_code = ask_nonempty("Room code: ").upper()
    room_name = ask_nonempty("Room name: ")
    building = input("Building: ").strip() or None
    floor_no = ask_int("Floor number: ")
    capacity = ask_int("Capacity: ", minimum=1)

    room_type = input(
        "Room type (CLASSROOM/LAB/LECTURE_HALL/OTHER): "
    ).strip().upper()

    allowed_types = ("CLASSROOM", "LAB", "LECTURE_HALL", "OTHER")

    if room_type not in allowed_types:
        print("Invalid room type.")
        return

    try:
        execute_sql(
            """
            INSERT INTO classrooms
                (room_code, room_name, building, floor_no,
                 room_type, capacity, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'AVAILABLE')
            """,
            (
                room_code,
                room_name,
                building,
                floor_no,
                room_type,
                capacity,
            ),
        )

        print("Classroom added successfully.")

    except Error as error:
        print("Could not add classroom:", error)


def update_classroom():
    heading("UPDATE CLASSROOM")

    classroom = choose_classroom(active_only=False)

    if not classroom:
        return

    room_name = input(
        f"Room name [{classroom['room_name']}]: "
    ).strip() or classroom["room_name"]

    capacity = input(
        f"Capacity [{classroom['capacity']}]: "
    ).strip()

    building = input(
        f"Building [{classroom['building'] or ''}]: "
    ).strip()

    floor_no = input(
        f"Floor [{classroom['floor_no']}]: "
    ).strip()

    status = input(
        f"Status [{classroom['status']}] (AVAILABLE/MAINTENANCE/INACTIVE): "
    ).strip().upper() or classroom["status"]

    if status not in ("AVAILABLE", "MAINTENANCE", "INACTIVE"):
        print("Invalid status.")
        return

    try:
        capacity_value = (
            int(capacity) if capacity else classroom["capacity"]
        )

        floor_value = (
            int(floor_no) if floor_no else classroom["floor_no"]
        )

        if capacity_value < 1:
            print("Capacity must be at least 1.")
            return

        execute_sql(
            """
            UPDATE classrooms
            SET room_name = %s,
                capacity = %s,
                building = %s,
                floor_no = %s,
                status = %s
            WHERE classroom_id = %s
            """,
            (
                room_name,
                capacity_value,
                building or None,
                floor_value,
                status,
                classroom["classroom_id"],
            ),
        )

        print("Classroom updated successfully.")

    except (Error, ValueError) as error:
        print("Could not update classroom:", error)


def remove_classroom():
    heading("REMOVE CLASSROOM")

    classroom = choose_classroom(active_only=False)

    if not classroom:
        return

    linked = fetch_one(
        """
        SELECT
            (SELECT COUNT(*) FROM bookings
             WHERE classroom_id = %s) AS booking_count,
            (SELECT COUNT(*) FROM booking_requests
             WHERE requested_classroom_id = %s) AS request_count,
            (SELECT COUNT(*) FROM timetable_entries te
             JOIN timetables t ON t.timetable_id = te.timetable_id
             WHERE t.classroom_id = %s) AS timetable_count
        """,
        (
            classroom["classroom_id"],
            classroom["classroom_id"],
            classroom["classroom_id"],
        ),
    )

    if (
        linked["booking_count"]
        or linked["request_count"]
        or linked["timetable_count"]
    ):
        print("This classroom has linked records and cannot be deleted.")
        print("Set its status to INACTIVE instead.")
        return

    confirm = input(
        f"Delete {classroom['room_code']}? Type YES to confirm: "
    ).strip()

    if confirm != "YES":
        print("Deletion cancelled.")
        return

    try:
        execute_sql(
            "DELETE FROM classrooms WHERE classroom_id = %s",
            (classroom["classroom_id"],),
        )
        print("Classroom deleted.")

    except Error as error:
        print("Could not delete classroom:", error)


def show_users():
    heading("REGISTERED USERS")

    users = fetch_all(
        """
        SELECT u.user_id, u.full_name, u.email, u.role,
               u.is_active, f.employee_code, f.department
        FROM users u
        LEFT JOIN faculty f ON f.user_id = u.user_id
        ORDER BY u.role, u.full_name
        """
    )

    display_table(
        users,
        [
            ("user_id", "ID"),
            ("full_name", "Name"),
            ("email", "Email"),
            ("role", "Role"),
            ("employee_code", "Employee code"),
            ("department", "Department"),
            ("is_active", "Active"),
        ],
    )


def toggle_user_status():
    heading("ACTIVATE / DEACTIVATE USER")

    users = fetch_all(
        """
        SELECT user_id, full_name, email, role, is_active
        FROM users
        ORDER BY user_id
        """
    )

    display_table(
        users,
        [
            ("user_id", "ID"),
            ("full_name", "Name"),
            ("email", "Email"),
            ("role", "Role"),
            ("is_active", "Active"),
        ],
    )

    user_id = ask_int("User ID: ", minimum=1)

    target = fetch_one(
        "SELECT user_id, role, is_active FROM users WHERE user_id = %s",
        (user_id,),
    )

    if not target:
        print("User not found.")
        return

    if target["role"] == "ADMIN":
        admins = fetch_one(
            """
            SELECT COUNT(*) AS total
            FROM users
            WHERE role = 'ADMIN' AND is_active = 1
            """
        )

        if target["is_active"] and admins["total"] <= 1:
            print("The last active administrator cannot be deactivated.")
            return

    new_status = 0 if target["is_active"] else 1

    try:
        execute_sql(
            "UPDATE users SET is_active = %s WHERE user_id = %s",
            (new_status, user_id),
        )

        print("User status updated.")

    except Error as error:
        print("Could not update user:", error)


def get_algorithm():
    return "FCFS"

def booking_request_details(request_id):
    return fetch_one(
        """
        SELECT br.request_id, br.faculty_id, br.requested_classroom_id,
               br.requested_date, br.recurrence_end_date,
               br.start_time, br.end_time, br.required_capacity,
               br.priority, br.booking_type, br.status, br.reason,
               f.employee_code, u.full_name,
               c.room_code, c.capacity
        FROM booking_requests br
        JOIN faculty f ON f.faculty_id = br.faculty_id
        JOIN users u ON u.user_id = f.user_id
        JOIN classrooms c
          ON c.classroom_id = br.requested_classroom_id
        WHERE br.request_id = %s
        """,
        (request_id,),
    )


def request_weekdays(request_id):
    rows = fetch_all(
        """
        SELECT day_of_week
        FROM booking_request_days
        WHERE request_id = %s
        """,
        (request_id,),
    )

    return {row["day_of_week"] for row in rows}


def dates_for_request(request):
    start_date = request["requested_date"]
    end_date = request["recurrence_end_date"] or start_date

    if isinstance(start_date, datetime):
        start_date = start_date.date()

    if isinstance(end_date, datetime):
        end_date = end_date.date()

    weekdays = request_weekdays(request["request_id"])

    if not weekdays:
        return [start_date]

    result = []
    current = start_date

    while current <= end_date:
        if current.strftime("%A") in weekdays:
            result.append(current)

        current += timedelta(days=1)

        if len(result) > 1000:
            raise ValueError("Recurrence exceeds 1000 dates.")

    return result


def list_booking_requests(status=None):
    sql = """
        SELECT br.request_id, u.full_name, c.room_code,
               br.requested_date, br.recurrence_end_date,
               br.start_time, br.end_time, br.required_capacity,
               br.priority, br.booking_type, br.status
        FROM booking_requests br
        JOIN faculty f ON f.faculty_id = br.faculty_id
        JOIN users u ON u.user_id = f.user_id
        JOIN classrooms c
          ON c.classroom_id = br.requested_classroom_id
    """

    params = ()

    if status:
        sql += " WHERE br.status = %s"
        params = (status,)

    sql += " ORDER BY br.request_id"

    return fetch_all(sql, params)


def show_booking_requests(status=None):
    heading("BOOKING REQUESTS")

    requests = list_booking_requests(status)

    display_table(
        requests,
        [
            ("request_id", "ID"),
            ("full_name", "Faculty"),
            ("room_code", "Room"),
            ("requested_date", "Start date"),
            ("recurrence_end_date", "End date"),
            ("start_time", "Start"),
            ("end_time", "End"),
            ("required_capacity", "Students"),
            ("priority", "Priority"),
            ("booking_type", "Type"),
            ("status", "Status"),
        ],
    )

    return requests


def check_room_with_c(room, booking_day, start_time, end_time, students):
    payload = {
        "operation": "check_room",
        "rooms": [
            {
                "id": str(room["classroom_id"]),
                "name": room["room_code"],
                "capacity": int(room["capacity"]),
                "status": room["status"],
            }
        ],
        "bookings": [],
        "room": str(room["classroom_id"]),
        "day": booking_day.isoformat(),
        "start": start_time.strftime("%H:%M"),
        "end": end_time.strftime("%H:%M"),
        "students": int(students),
    }

    result = subprocess.run(
        [C_EXECUTABLE],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or "C scheduling engine failed."
        )

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "The C scheduling engine returned invalid JSON."
        ) from error


def validate_booking_date(
    classroom_id,
    faculty_id,
    booking_day,
    start_time,
    end_time,
    students,
    exclude_booking_id=None,
):
    if end_time <= start_time:
        return False, "End time must be later than start time."

    if booking_day < date.today():
        return False, "Past booking dates are not allowed."

    room = fetch_one(
        """
        SELECT classroom_id, room_code, capacity, status
        FROM classrooms
        WHERE classroom_id = %s
        """,
        (classroom_id,),
    )

    if not room:
        return False, "Classroom not found."

    if room["status"] != "AVAILABLE":
        return False, "Classroom is not available."

    if students > room["capacity"]:
        return False, "The classroom capacity is insufficient."

    booking_day_value = booking_day.isoformat()
    start_value = start_time.strftime("%H:%M:%S")
    end_value = end_time.strftime("%H:%M:%S")

    connection = connect_db()
    cursor = connection.cursor(dictionary=True)

    try:
        sql = """
            SELECT booking_id, faculty_id, classroom_id,
                   start_time, end_time
            FROM bookings
            WHERE booking_date = %s
              AND status = 'CONFIRMED'
              AND start_time < %s
              AND end_time > %s
              AND (classroom_id = %s OR faculty_id = %s)
        """

        params = [
            booking_day_value,
            end_value,
            start_value,
            classroom_id,
            faculty_id,
        ]

        if exclude_booking_id is not None:
            sql += " AND booking_id <> %s"
            params.append(exclude_booking_id)

        cursor.execute(sql, tuple(params))
        conflicts = cursor.fetchall()

        for conflict in conflicts:
            if conflict["classroom_id"] == classroom_id:
                return False, "Classroom already has an overlapping booking."

            if conflict["faculty_id"] == faculty_id:
                return False, "Faculty member already has an overlapping booking."

        return True, "AVAILABLE"

    finally:
        cursor.close()
        connection.close()


def request_booking(user):
    heading("REQUEST CLASSROOM BOOKING")

    classroom = choose_classroom(active_only=True)

    if not classroom:
        return

    booking_type = input(
        "Booking type (TEMPORARY/PERMANENT): "
    ).strip().upper()

    if booking_type not in ("TEMPORARY", "PERMANENT"):
        print("Invalid booking type.")
        return

    recurrence_end_date = None
    selected_days = set()

    if booking_type == "TEMPORARY":
        booking_day = ask_date("Booking date (YYYY-MM-DD): ")

    else:
        booking_day = ask_date("Start date (YYYY-MM-DD): ")

        recurrence_end = input(
            "Permanent booking end date (YYYY-MM-DD): "
        ).strip()

        try:
            recurrence_end_date = date.fromisoformat(recurrence_end)

            if recurrence_end_date < booking_day:
                print("End date must not precede the start date.")
                return

        except ValueError:
            print("Invalid end date.")
            return

        print("\nSelect recurring weekdays:")
        for key, weekday in WEEKDAYS.items():
            print(f"{key}. {weekday}")

        print("Enter weekday numbers separated by commas, e.g. 1,3,5.")
        values = input("Weekdays: ").strip()

        try:
            numbers = {value.strip() for value in values.split(",")}

            if not numbers or "" in numbers:
                raise ValueError

            if not numbers.issubset(WEEKDAYS.keys()):
                raise ValueError

            selected_days = {WEEKDAYS[value] for value in numbers}

        except ValueError:
            print("Invalid weekday selection.")
            return

    start_time = ask_time("Start time (HH:MM): ")
    end_time = ask_time("End time (HH:MM): ")

    if end_time <= start_time:
        print("End time must be later than start time.")
        return

    students = ask_int("Required student capacity: ", minimum=1)
    priority = ask_int(
        "Priority (1-10, higher means more important): ", 1, 10
    )

    if students > classroom["capacity"]:
        print("Requested capacity exceeds the selected classroom's capacity.")

        try:
            result = check_room_with_c(
                classroom,
                booking_day,
                start_time,
                end_time,
                students,
            )

            print("Scheduler result:", result.get("message", "Unavailable"))
            print("Alternative classrooms:", result.get("alternatives", []))

        except (RuntimeError, OSError) as error:
            print(error)

        return

    faculty_id = user["faculty_id"]

    try:
        dates = []
        current = booking_day
        last_date = recurrence_end_date or booking_day

        while current <= last_date:
            if (
                booking_type == "TEMPORARY"
                or current.strftime("%A") in selected_days
            ):
                dates.append(current)

            current += timedelta(days=1)

            if len(dates) > 1000:
                print("Recurrence is too long.")
                return

        if not dates:
            print("No dates match your selected weekdays.")
            return

        for occurrence in dates:
            valid, message = validate_booking_date(
                classroom["classroom_id"],
                faculty_id,
                occurrence,
                start_time,
                end_time,
                students,
            )

            if not valid:
                print(f"{occurrence}: {message}")
                return

        connection = connect_db()
        cursor = connection.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO booking_requests
                    (faculty_id, requested_classroom_id,
                     requested_date, recurrence_end_date,
                     start_time, end_time, required_capacity,
                     priority, booking_type, status, reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDING', NULL)
                """,
                (
                    faculty_id,
                    classroom["classroom_id"],
                    booking_day,
                    recurrence_end_date,
                    start_time,
                    end_time,
                    students,
                    priority,
                    booking_type,
                ),
            )

            request_id = cursor.lastrowid

            for weekday in sorted(selected_days):
                cursor.execute(
                    """
                    INSERT INTO booking_request_days
                        (request_id, day_of_week)
                    VALUES (%s, %s)
                    """,
                    (request_id, weekday),
                )

            connection.commit()

            print("\nBooking request submitted successfully.")
            print("Request ID:", request_id)
            print("Booking type:", booking_type)
            print("processing request using",get_algorithm(),"...")
            process_one_request(request_id)

        except Error:
            connection.rollback()
            raise

        finally:
            cursor.close()
            connection.close()

    except (Error, RuntimeError, OSError, ValueError) as error:
        print("Could not submit request:", error)
def view_my_bookings(user):
    heading("MY BOOKINGS")

    bookings = fetch_all(
        """
        SELECT b.booking_id, c.room_code, b.booking_date,
               b.start_time, b.end_time, b.status,
               br.booking_type
        FROM bookings b
        JOIN classrooms c ON c.classroom_id = b.classroom_id
        JOIN booking_requests br ON br.request_id = b.request_id
        WHERE b.faculty_id = %s
        ORDER BY b.booking_date, b.start_time
        """,
        (user["faculty_id"],),
    )

    display_table(
        bookings,
        [
            ("booking_id", "Booking ID"),
            ("room_code", "Room"),
            ("booking_date", "Date"),
            ("start_time", "Start"),
            ("end_time", "End"),
            ("status", "Status"),
            ("booking_type", "Type"),
        ],
    )


def view_my_requests(user):
    heading("MY BOOKING REQUESTS")

    requests = fetch_all(
        """
        SELECT br.request_id, c.room_code, br.requested_date,
               br.recurrence_end_date, br.start_time, br.end_time,
               br.booking_type, br.status, br.reason
        FROM booking_requests br
        JOIN classrooms c
          ON c.classroom_id = br.requested_classroom_id
        WHERE br.faculty_id = %s
        ORDER BY br.request_id DESC
        """,
        (user["faculty_id"],),
    )

    display_table(
        requests,
        [
            ("request_id", "Request ID"),
            ("room_code", "Room"),
            ("requested_date", "Start date"),
            ("recurrence_end_date", "End date"),
            ("start_time", "Start"),
            ("end_time", "End"),
            ("booking_type", "Type"),
            ("status", "Status"),
            ("reason", "Reason"),
        ],
    )


def process_booking_requests():
    heading("PROCESS PENDING REQUESTS")

    requests = show_booking_requests("PENDING")

    if not requests:
        return

    algorithm = get_algorithm()

    print("\nCurrent algorithm:", algorithm)
    print("1. Process one request")
    print("2. Process all pending requests")

    choice = input("Choose: ").strip()

    if choice == "1":
        request_id = ask_int("Request ID: ", minimum=1)
        process_one_request(request_id)
    elif choice == "2":
        process_all_pending_requests()
    else:
        print("Invalid choice.")


def process_one_request(request_id):
    request = booking_request_details(request_id)

    if not request:
        print("Request not found.")
        return

    if request["status"] != "PENDING":
        print("Only pending requests can be processed.")
        return

    process_requests([request])


def process_all_pending_requests():
    requests = list_booking_requests("PENDING")

    if not requests:
        print("No pending requests.")
        return

    detailed = []

    for item in requests:
        request = booking_request_details(item["request_id"])

        if request:
            detailed.append(request)

    process_requests(detailed)

def time_to_minutes(value):
    if hasattr(value, "total_seconds"):
        return int(value.total_seconds() // 60)
    if hasattr(value, "hour") and hasattr(value, "minute"):
        return value.hour * 60 + value.minute
    parts = str(value).split(":")
    return int(parts[0]) * 60 + int(parts[1])

def process_requests(requests):
    algorithm = get_algorithm()
    requests = sorted(
        requests,
        key=lambda request: request["request_id"]
    )
    rooms = fetch_all(
        """
        SELECT classroom_id, room_code, capacity, status
        FROM classrooms
        WHERE status = 'AVAILABLE'
        """
    )

    all_bookings = fetch_all(
        """
        SELECT booking_id, faculty_id, classroom_id,
               booking_date, start_time, end_time, status
        FROM bookings
        WHERE status = 'CONFIRMED'
        """
    )
    pending = []
    for request in requests:
        try:
            dates = dates_for_request(request)
        except ValueError as error:
            print(f"Request {request['request_id']}: {error}")
            continue

        for booking_day in dates:
            pending.append({
                "id": str(request["request_id"]),
                "faculty": str(request["faculty_id"]),
                "room": str(request["requested_classroom_id"]),
                "day": booking_day.isoformat(),
                "start": str(request["start_time"])[:5],
                "end": str(request["end_time"])[:5],
                "students": int(request["required_capacity"]),
                "priority": int(request["priority"]),
                "processing_time": (
    time_to_minutes(request["end_time"])
    - time_to_minutes(request["start_time"])
),
            })
    if not pending:
        print("No valid booking occurrences to process.")
        return
    c_rooms = [
        {
            "id": str(room["classroom_id"]),
            "name": room["room_code"],
            "capacity": int(room["capacity"]),
            "status": room["status"],
        }
        for room in rooms
    ]
    c_bookings = [
        {
            "id": str(booking["booking_id"]),
            "faculty": str(booking["faculty_id"]),
            "room": str(booking["classroom_id"]),
            "day": str(booking["booking_date"]),
            "start": str(booking["start_time"])[:5],
            "end": str(booking["end_time"])[:5],
            "status": booking["status"],
        }
        for booking in all_bookings
    ]
    payload = {
        "operation": "schedule",
        "algorithm": algorithm,
        "rooms": c_rooms,
        "bookings": c_bookings,
        "pending": pending,
    }
    try:
        result = subprocess.run(
            [C_EXECUTABLE],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=False,
        )

        if result.returncode != 0:
            print("C scheduler failed!")
            print("Return code:", result.returncode)
            print("STDOUT:", repr(result.stdout))
            print("STDERR:", repr(result.stderr))
            return

        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            print("Invalid JSON from C scheduler:", error)
            return

        if not output.get("success"):
            print("Scheduler error:", output.get("message"))
            return

        grouped = {}

        for result_row in output.get("results", []):
            request_id = int(result_row["id"])
            grouped.setdefault(request_id, []).append(result_row)

        for request in requests:
            request_id = request["request_id"]
            results = grouped.get(request_id, [])

            if results:
                process_request_results(request, results)
    except (OSError, Error, ValueError, KeyError, TypeError) as error:

        
        print("Could not process requests:", error)
def process_request_results(request, results):
    request_id = request["request_id"]
    approved_dates = []
    rejected_dates = []
    for result in results:
        if result.get("status") == "ALLOCATED":
            approved_dates.append(result)
        else:
            rejected_dates.append(result)

    # If any occurrence is rejected, reject the entire request.
    if rejected_dates or not approved_dates:
        if rejected_dates:
            reasons = "; ".join(
                dict.fromkeys(
                    result.get("reason") or "Booking unavailable"
                    for result in rejected_dates
                )
            )
        else:
            reasons = "The scheduler did not allocate any booking dates."

        connection = connect_db()
        cursor = connection.cursor()

        try:
            cursor.execute(
                """
                UPDATE booking_requests
                SET status = 'REJECTED', reason = %s
                WHERE request_id = %s AND status = 'PENDING'
                """,
                (reasons, request_id),
            )

            connection.commit()

            if cursor.rowcount > 0:
                print(f"Request {request_id} REJECTED.")
                print("Reason:", reasons)
            else:
                print(
                    f"Request {request_id} was not updated. "
                    "It may no longer be pending."
                )

        except Error as error:
            connection.rollback()
            print(
                f"Could not reject request {request_id}:",
                error,
            )

        finally:
            cursor.close()
            connection.close()

        return

    # All occurrences were allocated. Save the bookings.
    connection = connect_db()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT status
            FROM booking_requests
            WHERE request_id = %s
            FOR UPDATE
            """,
            (request_id,),
        )

        current = cursor.fetchone()

        if not current or current[0] != "PENDING":
            connection.rollback()
            print(f"Request {request_id} is no longer pending.")
            return

        for result in approved_dates:
            result_date = result.get("day")

            if not result_date:
                raise ValueError(
                    f"Scheduler returned no date for request {request_id}."
                )

            cursor.execute(
                """
                INSERT INTO bookings
                    (
                        request_id,
                        classroom_id,
                        faculty_id,
                        booking_date,
                        start_time,
                        end_time,
                        status,
                        created_by
                    )
                VALUES (%s, %s, %s, %s, %s, %s, 'CONFIRMED', %s)
                """,
                (
                    request_id,
                    request["requested_classroom_id"],
                    request["faculty_id"],
                    result_date,
                    request["start_time"],
                    request["end_time"],
                    1,
                ),
            )

            booking_id = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO booking_history
                    (booking_id, action, performed_by, notes)
                VALUES (%s, 'APPROVED', %s, %s)
                """,
                (
                    booking_id,
                    1,
                    f"Automatically approved using "
                    f"{get_algorithm()} scheduling.",
                ),
            )

        cursor.execute(
            """
            UPDATE booking_requests
            SET status = 'APPROVED', reason = NULL
            WHERE request_id = %s AND status = 'PENDING'
            """,
            (request_id,),
        )

        connection.commit()

        print(
            f"Request {request_id} APPROVED: "
            f"{len(approved_dates)} occurrence(s)."
        )

    except (Error, ValueError) as error:
        connection.rollback()
        print(
            f"Could not process request {request_id}:",
            error,
        )

    finally:
        cursor.close()
        connection.close()
def reject_booking_request():
    heading("REJECT BOOKING REQUEST")

    show_booking_requests("PENDING")

    request_id = ask_int("Request ID to reject: ", minimum=1)
    reason = ask_nonempty("Reason for rejection: ")

    request = booking_request_details(request_id)

    if not request or request["status"] != "PENDING":
        print("Pending request not found.")
        return

    connection = connect_db()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE booking_requests
            SET status = 'REJECTED', reason = %s
            WHERE request_id = %s AND status = 'PENDING'
            """,
            (reason, request_id),
        )

        connection.commit()

        if cursor.rowcount:
            print("Request rejected.")
        else:
            print("Request was not changed.")

    except Error as error:
        connection.rollback()
        print("Could not reject request:", error)

    finally:
        cursor.close()
        connection.close()


def cancel_my_request(user):
    heading("CANCEL MY PENDING REQUEST")

    view_my_requests(user)

    request_id = ask_int("Request ID: ", minimum=1)

    request = fetch_one(
        """
        SELECT request_id, status
        FROM booking_requests
        WHERE request_id = %s AND faculty_id = %s
        """,
        (request_id, user["faculty_id"]),
    )

    if not request or request["status"] != "PENDING":
        print("Only your pending requests can be cancelled.")
        return

    try:
        execute_sql(
            """
            UPDATE booking_requests
            SET status = 'CANCELLED'
            WHERE request_id = %s AND faculty_id = %s
            """,
            (request_id, user["faculty_id"]),
        )

        print("Request cancelled.")

    except Error as error:
        print("Could not cancel request:", error)


def cancel_booking(user):
    heading("CANCEL BOOKING")

    bookings = fetch_all(
        """
        SELECT booking_id, classroom_id, booking_date,
               start_time, end_time, status
        FROM bookings
        WHERE faculty_id = %s AND status = 'CONFIRMED'
        ORDER BY booking_date, start_time
        """,
        (user["faculty_id"],),
    )

    display_table(
        bookings,
        [
            ("booking_id", "Booking ID"),
            ("classroom_id", "Room ID"),
            ("booking_date", "Date"),
            ("start_time", "Start"),
            ("end_time", "End"),
            ("status", "Status"),
        ],
    )

    booking_id = ask_int("Booking ID to cancel: ", minimum=1)

    connection = connect_db()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT booking_id, request_id
            FROM bookings
            WHERE booking_id = %s
              AND faculty_id = %s
              AND status = 'CONFIRMED'
            FOR UPDATE
            """,
            (booking_id, user["faculty_id"]),
        )

        booking = cursor.fetchone()

        if not booking:
            connection.rollback()
            print("Booking not found.")
            return

        cursor.execute(
            """
            UPDATE bookings
            SET status = 'CANCELLED'
            WHERE booking_id = %s
            """,
            (booking_id,),
        )

        cursor.execute(
            """
            INSERT INTO booking_history
                (booking_id, action, performed_by, notes)
            VALUES (%s, 'CANCELLED', %s, %s)
            """,
            (
                booking_id,
                user["user_id"],
                "Cancelled by faculty.",
            ),
        )

        cursor.execute(
            """
            SELECT COUNT(*) AS remaining
            FROM bookings
            WHERE request_id = %s AND status = 'CONFIRMED'
            """,
            (booking["request_id"],),
        )

        remaining = cursor.fetchone()["remaining"]

        if remaining == 0:
            cursor.execute(
                """
                UPDATE booking_requests
                SET status = 'CANCELLED'
                WHERE request_id = %s
                """,
                (booking["request_id"],),
            )

        connection.commit()
        print("Booking cancelled.")

    except Error as error:
        connection.rollback()
        print("Could not cancel booking:", error)

    finally:
        cursor.close()
        connection.close()


def choose_timetable_classroom():
    heading("SELECT CLASSROOM TIMETABLE")

    classrooms = fetch_all(
        """
        SELECT classroom_id, room_code, room_name, status
        FROM classrooms
        ORDER BY room_code
        """
    )

    display_table(
        classrooms,
        [
            ("classroom_id", "ID"),
            ("room_code", "Code"),
            ("room_name", "Name"),
            ("status", "Status"),
        ],
    )

    if not classrooms:
        return None

    classroom_id = ask_int("Classroom ID: ", minimum=1)

    classroom = fetch_one(
        """
        SELECT classroom_id, room_code, room_name
        FROM classrooms
        WHERE classroom_id = %s
        """,
        (classroom_id,),
    )

    if not classroom:
        print("Classroom not found.")
        return None

    return classroom


def view_timetable():
    heading("VIEW CLASSROOM TIMETABLE")

    # Select a classroom by its name/code, not its ID.
    classroom = choose_timetable_classroom()

    if not classroom:
        return

    # Fetch the active timetable for the selected classroom.
    selected = fetch_one(
        """
        SELECT timetable_id, revision_no
        FROM timetables
        WHERE classroom_id = %s
          AND status = 'ACTIVE'
        ORDER BY revision_no DESC
        LIMIT 1
        """,
        (classroom["classroom_id"],),
    )

    if not selected:
        print("No active timetable exists for this classroom.")
        return

    # Fetch the timetable entries.
    entries = fetch_all(
        """
        SELECT
            te.day_of_week,
            ts.slot_label,
            ts.start_time,
            ts.end_time,
            s.section_name,
            COALESCE(sub.subject_name, te.activity_name) AS subject,
            u.full_name AS faculty_name,
            te.activity_type,
            te.activity_name
        FROM timetable_entries AS te
        JOIN time_slots AS ts
            ON ts.slot_id = te.slot_id
        JOIN sections AS s
            ON s.section_id = te.section_id
        LEFT JOIN subjects AS sub
            ON sub.subject_id = te.subject_id
        JOIN faculty AS f
            ON f.faculty_id = te.faculty_id
        JOIN users AS u
            ON u.user_id = f.user_id
        WHERE te.timetable_id = %s
        ORDER BY
            FIELD(
                te.day_of_week,
                'MONDAY', 'TUESDAY', 'WEDNESDAY',
                'THURSDAY', 'FRIDAY', 'SATURDAY'
            ),
            ts.slot_order
        """,
        (selected["timetable_id"],),
    )

    print(f"\nCLASSROOM TIMETABLE: {classroom['room_name']}")
    print(f"Revision: {selected['revision_no']}")

    if not entries:
        print("No timetable entries found for this classroom.")
        return

    display_table(
        entries,
        [
            ("day_of_week", "Day"),
            ("slot_label", "Time"),
            ("section_name", "Section"),
            ("subject", "Subject"),
            ("faculty_name", "Faculty"),
            ("activity_type", "Activity Type"),
        ],
    )
def create_timetable():
    heading("CREATE CLASSROOM TIMETABLE")

    classroom = choose_timetable_classroom()

    if not classroom:
        return

    effective_from = ask_date("Effective from (YYYY-MM-DD): ")
    effective_to_text = input(
        "Effective to (YYYY-MM-DD), or Enter for no end date: "
    ).strip()

    effective_to = None

    if effective_to_text:
        try:
            effective_to = date.fromisoformat(effective_to_text)

            if effective_to < effective_from:
                print("End date cannot precede the start date.")
                return

        except ValueError:
            print("Invalid end date.")
            return

    sections = fetch_all(
        """
        SELECT section_id, section_name, academic_year,
               year_level, semester
        FROM sections
        ORDER BY section_name
        """
    )

    slots = fetch_all(
        """
        SELECT slot_id, slot_label, start_time, end_time, slot_order
        FROM time_slots
        ORDER BY slot_order
        """
    )

    faculty = fetch_all(
        """
        SELECT f.faculty_id, u.full_name, f.employee_code
        FROM faculty f
        JOIN users u ON u.user_id = f.user_id
        WHERE u.is_active = 1
        ORDER BY u.full_name
        """
    )

    subjects = fetch_all(
        """
        SELECT subject_id, subject_code, subject_name
        FROM subjects
        ORDER BY subject_code
        """
    )

    if not sections:
        print("No sections are available.")
        return

    if not slots:
        print("No time slots are configured.")
        return

    if not faculty:
        print("No active faculty profiles exist.")
        return

    if not subjects:
        print("No subjects are configured.")
        return

    def choose_item(items, label, display):
        print(f"\n{label}:")
        for index, item in enumerate(items, start=1):
            print(f"{index}. {display(item)}")

        choice = ask_int(
            f"Choose {label.lower()} (0 to cancel): ",
            minimum=0,
        )

        if choice == 0:
            return None

        if choice > len(items):
            print("Invalid selection.")
            return None

        return items[choice - 1]

    revision = fetch_one(
        """
        SELECT COALESCE(MAX(revision_no), 0) + 1 AS next_revision
        FROM timetables
        WHERE classroom_id = %s
        """,
        (classroom["classroom_id"],),
    )["next_revision"]

    connection = connect_db()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO timetables
                (classroom_id, revision_no, effective_from,
                 effective_to, status)
            VALUES (%s, %s, %s, %s, 'DRAFT')
            """,
            (
                classroom["classroom_id"],
                revision,
                effective_from,
                effective_to,
            ),
        )

        timetable_id = cursor.lastrowid
        connection.commit()

    except Error as error:
        connection.rollback()
        print("Could not create timetable:", error)
        return

    finally:
        cursor.close()
        connection.close()

    print(
        f"\nCreating timetable for classroom: "
        f"{classroom['room_name']}"
    )
    print("Enter timetable entries. Enter 0 for Day to finish.")

    while True:
        print("\nDays:")
        for key, weekday in WEEKDAYS.items():
            print(f"{key}. {weekday}")

        day_choice = input("Day (0 to finish): ").strip()

        if day_choice == "0":
            break

        if day_choice not in WEEKDAYS:
            print("Invalid day.")
            continue

        section = choose_item(
            sections,
            "Sections",
            lambda item: item["section_name"],
        )
        if not section:
            continue

        slot = choose_item(
            slots,
            "Time slots",
            lambda item: (
                f'{item["slot_label"]} '
                f'({item["start_time"]}–{item["end_time"]})'
            ),
        )
        if not slot:
            continue

        selected_faculty = choose_item(
            faculty,
            "Faculty",
            lambda item: item["full_name"],
        )
        if not selected_faculty:
            continue

        subject = choose_item(
            subjects,
            "Subjects",
            lambda item: (
                f'{item["subject_name"]} ({item["subject_code"]})'
            ),
        )
        if not subject:
            continue

        activity_type = input(
            "Activity type (THEORY/LAB/ELECTIVE/OTHER): "
        ).strip().upper()

        if activity_type not in (
            "THEORY", "LAB", "ELECTIVE", "OTHER"
        ):
            print("Invalid activity type.")
            continue

        activity_name = ask_nonempty("Activity name: ")

        try:
            execute_sql(
                """
                INSERT INTO timetable_entries
                    (timetable_id, day_of_week, slot_id, section_id,
                     subject_id, faculty_id, activity_type,
                     activity_name, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL)
                """,
                (
                    timetable_id,
                    WEEKDAYS[day_choice].upper(),
                    slot["slot_id"],
                    section["section_id"],
                    subject["subject_id"],
                    selected_faculty["faculty_id"],
                    activity_type,
                    activity_name,
                ),
            )

            print("Entry added.")

        except Error as error:
            print("Could not add entry:", error)

    print(
        f"\nTimetable for {classroom['room_name']} "
        f"saved as DRAFT."
    )
    print("Activate it when you are ready to use it.")

def activate_timetable():
    heading("ACTIVATE TIMETABLE")

    classroom = choose_timetable_classroom()

    if not classroom:
        return

    timetables = fetch_all(
        """
        SELECT timetable_id, revision_no, effective_from,
               effective_to, status
        FROM timetables
        WHERE classroom_id = %s
        ORDER BY revision_no DESC
        """,
        (classroom["classroom_id"],),
    )

    display_table(
        timetables,
        [
            ("timetable_id", "ID"),
            ("revision_no", "Revision"),
            ("effective_from", "Start"),
            ("effective_to", "End"),
            ("status", "Status"),
        ],
    )

    timetable_id = ask_int("Timetable ID to activate: ", minimum=1)

    selected = next(
        (
            item for item in timetables
            if item["timetable_id"] == timetable_id
        ),
        None,
    )

    if not selected:
        print("Invalid timetable ID.")
        return

    if selected["status"] == "ARCHIVED":
        print("An archived timetable cannot be activated.")
        return

    entries = fetch_one(
        """
        SELECT COUNT(*) AS total
        FROM timetable_entries
        WHERE timetable_id = %s
        """,
        (timetable_id,),
    )

    if entries["total"] == 0:
        print("Add timetable entries before activating.")
        return

    connection = connect_db()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE timetables
            SET status = 'ARCHIVED'
            WHERE classroom_id = %s AND status = 'ACTIVE'
            """,
            (classroom["classroom_id"],),
        )

        cursor.execute(
            """
            UPDATE timetables
            SET status = 'ACTIVE'
            WHERE timetable_id = %s
            """,
            (timetable_id,),
        )

        connection.commit()
        print("Timetable activated.")

    except Error as error:
        connection.rollback()
        print("Could not activate timetable:", error)

    finally:
        cursor.close()
        connection.close()


def faculty_menu(user):
    while True:
        heading(f"FACULTY MENU - {user['full_name']}")

        print("1. Request classroom booking")
        print("2. View my bookings")
        print("3. View my booking requests")
        print("4. Cancel a booking")
        print("5. Cancel a pending request")
        print("6. View classroom-wise timetable")
        print("7. Logout")

        choice = input("\nChoose an option: ").strip()

        try:
            if choice == "1":
                request_booking(user)
            elif choice == "2":
                view_my_bookings(user)
            elif choice == "3":
                view_my_requests(user)
            elif choice == "4":
                cancel_booking(user)
            elif choice == "5":
                cancel_my_request(user)
            elif choice == "6":
                view_timetable()
            elif choice == "7":
                return
            else:
                print("Invalid option.")

        except Error as error:
            print("Database error:", error)

        except (OSError, RuntimeError, ValueError) as error:
            print("Operation failed:", error)

        pause()


def admin_menu(user):
    while True:
        heading(f"ADMIN MENU - {user['full_name']}")

        print("1. View classrooms")
        print("2. View users")
        print("3. Activate/deactivate user")
        print("4. View booking requests")
        print("5. Process pending booking requests")
        print("6. Reject booking request")
        print("7. View classroom-wise timetable")
        print("8. Create classroom timetable")
        print("9. Activate timetable")
        print("10. Logout")

        choice = input("\nChoose an option: ").strip()

        try:
            if choice == "1":
                show_classrooms()
            elif choice == "2":
                show_users()
            elif choice == "3":
                toggle_user_status()
            elif choice == "4":
                show_booking_requests()
            elif choice == "5":
                process_booking_requests()
            elif choice == "6":
                reject_booking_request()
            elif choice == "7":
                view_timetable()
            elif choice == "8":
                create_timetable()
            elif choice == "9":
                activate_timetable()
            elif choice == "10":
                return
            else:
                print("Invalid option.")

        except Error as error:
            print("Database error:", error)

        except (OSError, RuntimeError, ValueError) as error:
            print("Operation failed:", error)

        pause()

def main():
    while True:
        heading("CampusResOS")

        print("1. Login")
        print("2. Sign Up")
        print("3. Exit")

        choice = input("\nChoose an option: ").strip()
        if choice == "1":
            heading("LOGIN")
            print("1. Login as Admin")
            print("2. Login as Faculty")
            print("3. Exit")
            role_choice = input("\nChoose an option: ").strip()
            if role_choice == "1":
                role = "ADMIN"
            elif role_choice == "2":
                role = "FACULTY"
            elif role_choice == "3":
                print("Exiting CampusResOS.")
                sys.exit(0)
            else:
                print("Invalid option.")
                pause()
                continue

            try:
                user = login(role)

                if user:
                    if role == "ADMIN":
                        admin_menu(user)
                    else:
                        faculty_menu(user)

            except Error as error:
                print("Database connection failed:", error)

            pause()

        # SIGN-UP MENU
        elif choice == "2":
            heading("SIGN UP")

            print("1. Sign Up as Admin")
            print("2. Sign Up as Faculty")
            print("3. Exit")

            role_choice = input("\nChoose an option: ").strip()

            if role_choice == "1":
                register_user("ADMIN")
            elif role_choice == "2":
                register_user("FACULTY")
            elif role_choice == "3":
                print("Exiting CampusResOS.")
                sys.exit(0)
            else:
                print("Invalid option.")
                pause()
                continue

            pause()

        elif choice == "3":
            print("Exiting CampusResOS.")
            sys.exit(0)

        else:
            print("Invalid option.")
            pause()


if __name__ == "__main__":
    main()