import json
import os
import hashlib
import hmac
import secrets
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_FILE = os.path.join(BASE_DIR, "users.json")
ROOM_FILE = os.path.join(BASE_DIR, "rooms.json")
BOOKING_FILE = os.path.join(BASE_DIR, "bookings.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
TIMETABLE_FILE = os.path.join(BASE_DIR, "timetable.json")

C_SOURCE = os.path.join(BASE_DIR, "c_module.c")
C_BINARY = os.path.join(BASE_DIR, "c_module")
def load_json(path, default):
    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

        return data if isinstance(data, type(default)) else default

    except (json.JSONDecodeError, OSError):
        print(f"Warning: could not read {os.path.basename(path)}.")
        return default
def save_json(path, data):
    temporary_path = path + ".tmp"

    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)

    os.replace(temporary_path, path)
def load_users():
    return load_json(USER_FILE, [])
def load_rooms():
    return load_json(ROOM_FILE, [])
def load_bookings():
    return load_json(BOOKING_FILE, [])
def load_timetable():
    return load_json(TIMETABLE_FILE, [])
def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)

    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        bytes.fromhex(salt),
        200000
    ).hex()

    return salt, hashed
def verify_password(password, salt, stored_hash):
    _, hashed = hash_password(password, salt)
    return hmac.compare_digest(hashed, stored_hash)
def ask_int(prompt, minimum=0):
    while True:
        try:
            value = int(input(prompt).strip())

            if value < minimum:
                print(f"Enter a number greater than or equal to {minimum}.")
                continue

            return value

        except ValueError:
            print("Please enter a valid whole number.")
def choose_role(action):
    while True:
        print(f"\n========== {action} ==========")
        print("1. Admin")
        print("2. Faculty")
        print("3. Back")

        choice = input("Choose your role: ").strip()

        if choice == "1":
            return "admin"
        elif choice == "2":
            return "faculty"
        elif choice == "3":
            return None

        print("Invalid choice. Try again.")
def signup():
    role = choose_role("SIGN UP")

    if role is None:
        return

    users = load_users()

    if role == "admin" and any(
        user.get("role") == "admin" for user in users
    ):
        print("An Admin account already exists.")
        return

    print(f"\n========== {role.upper()} SIGN UP ==========")

    fullname = input("Enter your full name: ").strip()

    if not fullname:
        print("Full name cannot be empty.")
        return

    if any(
        user.get("fullname", "").casefold() == fullname.casefold()
        and user.get("role") == role
        for user in users
    ):
        print("An account with this name and role already exists.")
        return

    while True:
        password = input("Create password (at least 8 characters): ")

        if len(password) < 8:
            print("Password must contain at least 8 characters.")
            continue

        confirm = input("Confirm password: ")

        if password != confirm:
            print("Passwords do not match.")
            continue

        break

    salt, digest = hash_password(password)

    users.append({
        "fullname": fullname,
        "role": role,
        "salt": salt,
        "password_hash": digest
    })

    save_json(USER_FILE, users)

    print("Registration successful. You can now log in.")
def compile_c_module():
    if not os.path.exists(C_SOURCE):
        print("ERROR: c_module.c must be beside terminal_app.py.")
        return False

    try:
        result = subprocess.run(
            ["gcc", "-pthread", C_SOURCE, "-o", C_BINARY],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print("C compilation failed:")
            print(result.stderr)
            return False

        return True

    except OSError as error:
        print("Could not run gcc:", error)
        print("Install a C compiler and try again.")
        return False
def call_c(payload):
    if (
        not os.path.exists(C_BINARY)
        or os.path.getmtime(C_SOURCE) > os.path.getmtime(C_BINARY)
    ):
        if not compile_c_module():
            return None

    try:
        result = subprocess.run(
            [C_BINARY],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            print("C module error:", result.stderr.strip())
            return None

        return json.loads(result.stdout)

    except (
        OSError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError
    ) as error:
        print("Could not communicate with C module:", error)
        return None
def print_rooms():
    rooms = load_rooms()

    if not rooms:
        print("No classrooms have been added yet.")
        return

    print("\n--- Classrooms ---")

    for room in rooms:
        print(
            f"ID: {room['id']} | "
            f"Name: {room['name']} | "
            f"Capacity: {room['capacity']}"
        )
def add_room():
    rooms = load_rooms()

    name = input("Classroom name/number: ").strip()

    if not name:
        print("Classroom name cannot be empty.")
        return

    if any(
        room.get("name", "").casefold() == name.casefold()
        for room in rooms
    ):
        print("That classroom already exists.")
        return

    capacity = ask_int("Room capacity: ", 1)

    numeric_ids = [
        int(room["id"])
        for room in rooms
        if str(room.get("id", "")).isdigit()
    ]

    next_id = str(max(numeric_ids + [0]) + 1)

    rooms.append({
        "id": next_id,
        "name": name,
        "capacity": capacity
    })

    save_json(ROOM_FILE, rooms)

    print("Classroom added successfully.")

def show_bookings(items=None):
    if items is None:
        items = load_bookings()

    if not items:
        print("No booking records found.")
        return

    for booking in items:
        print(
            f"\nID: {booking.get('id')} | "
            f"Faculty: {booking.get('faculty')} | "
            f"Room: {booking.get('room')} | "
            f"{booking.get('day')} "
            f"{booking.get('start')}-{booking.get('end')} | "
            f"Students: {booking.get('students')} | "
            f"Type: {booking.get('type')} | "
            f"Status: {booking.get('status')}"
        )

        if booking.get("reason"):
            print("Reason:", booking["reason"])

        if "waiting_time" in booking:
            print(
                "Scheduling waiting time:",
                booking.get("waiting_time"),
                "| Turnaround time:",
                booking.get("turnaround_time")
            )

        if booking.get("alternatives"):
            alternatives = ", ".join(
                f"{room.get('name')} "
                f"(capacity {room.get('capacity')})"
                for room in booking["alternatives"]
            )

            print("Alternative rooms:", alternatives)

def request_booking(fullname):
    rooms = load_rooms()

    if not rooms:
        print("No classrooms exist yet. Please contact the Admin.")
        return

    print_rooms()

    room = input("Enter classroom ID or exact name: ").strip()
    day = input("Day (e.g., Monday): ").strip()
    start = input("Start time in 24-hour HH:MM format: ").strip()
    end = input("End time in 24-hour HH:MM format: ").strip()
    course = input("Course/subject: ").strip()

    students = ask_int("Number of students: ", 1)

    booking_type = input(
        "Booking type (temporary/permanent): "
    ).strip().lower()

    if booking_type not in ("temporary", "permanent"):
        print("Enter either temporary or permanent.")
        return

    priority = ask_int(
        "Priority (1 = normal, higher number = more urgent): ", 1
    )

    processing_time = ask_int(
        "Processing-time value for scheduling: ", 1
    )

    bookings = load_bookings()

    numeric_ids = [
        int(booking["id"])
        for booking in bookings
        if str(booking.get("id", "")).isdigit()
    ]

    new_id = str(max(numeric_ids + [0]) + 1)

    new_booking = {
        "id": new_id,
        "faculty": fullname,
        "room": room,
        "day": day,
        "start": start,
        "end": end,
        "course": course,
        "students": students,
        "type": booking_type,
        "priority": priority,
        "processing_time": processing_time,
        "status": "PENDING",
        "reason": "",
        "alternatives": []
    }

    # Availability, capacity, conflict detection and suggestions
    # are performed by the C module.
    payload = {
        "operation": "check_room",
        "rooms": rooms,
        "bookings": bookings,
        "room": room,
        "day": day,
        "start": start,
        "end": end,
        "students": students
    }

    result = call_c(payload)

    if result is None:
        print("The C module could not check availability.")
        print("The booking request was not saved.")
        return

    print("\n--- C Module: Room Availability Check ---")
    print("Room exists:", result.get("room_found"))
    print("Capacity OK:", result.get("capacity_ok"))
    print("Available:", result.get("available"))
    print(result.get("message", ""))

    if result.get("conflicts"):
        print("Conflicting bookings:")

        for conflict in result["conflicts"]:
            print(
                f"Booking {conflict.get('booking_id')}: "
                f"{conflict.get('start')}-{conflict.get('end')} | "
                f"Faculty: {conflict.get('faculty')}"
            )

    if result.get("alternatives"):
        print("Possible alternative rooms:")

        for alternative in result["alternatives"]:
            print(
                f"{alternative.get('name')} | "
                f"Capacity: {alternative.get('capacity')}"
            )

    bookings.append(new_booking)
    save_json(BOOKING_FILE, bookings)

    print(
        f"Booking request #{new_id} saved as PENDING. "
        "The Admin must process it using the selected algorithm."
    )


def faculty_bookings(fullname):
    bookings = [
        booking for booking in load_bookings()
        if booking.get("faculty", "").casefold() == fullname.casefold()
    ]

    show_bookings(bookings)
def view_timetable():
    entries = load_timetable()

    if not entries:
        print("No timetable entries have been added yet.")
        return

    print("\n--- Timetable ---")

    for entry in entries:
        print(
            f"{entry.get('day')} | "
            f"{entry.get('start')}-{entry.get('end')} | "
            f"{entry.get('course')} | "
            f"Room: {entry.get('room')} | "
            f"Faculty: {entry.get('faculty')}"
        )


def add_timetable_entry():
    entries = load_timetable()

    entry = {
        "day": input("Day: ").strip(),
        "start": input("Start time (HH:MM): ").strip(),
        "end": input("End time (HH:MM): ").strip(),
        "course": input("Course/subject: ").strip(),
        "room": input("Room ID or name: ").strip(),
        "faculty": input("Faculty name: ").strip()
    }

    entries.append(entry)
    save_json(TIMETABLE_FILE, entries)

    print("Timetable entry added.")

def select_algorithm():
    settings = load_json(SETTINGS_FILE, {"algorithm": "FCFS"})

    print("\nSelect scheduling algorithm:")
    print("1. FCFS (First Come, First Served)")
    print("2. Priority Scheduling")

    choice = input("Choose: ").strip()

    if choice == "1":
        settings["algorithm"] = "FCFS"
    elif choice == "2":
        settings["algorithm"] = "PRIORITY"
    else:
        print("Invalid choice.")
        return

    save_json(SETTINGS_FILE, settings)

    print("Active algorithm set to", settings["algorithm"])


def process_pending():
    bookings = load_bookings()

    pending = [
        booking for booking in bookings
        if booking.get("status") == "PENDING"
    ]

    if not pending:
        print("There are no pending booking requests.")
        return

    settings = load_json(SETTINGS_FILE, {"algorithm": "FCFS"})
    algorithm = settings.get("algorithm", "FCFS")

    print(
        f"Processing {len(pending)} pending request(s) "
        f"using {algorithm} in the C/POSIX module..."
    )

    payload = {
        "operation": "schedule",
        "algorithm": algorithm,
        "rooms": load_rooms(),
        "bookings": bookings,
        "pending": pending
    }

    response = call_c(payload)

    if not response or not response.get("success"):
        print(
            "Scheduling failed:",
            (response or {}).get("message", "No response from C module.")
        )
        return

    results = {
        str(result.get("id")): result
        for result in response.get("results", [])
    }

    for booking in bookings:
        result = results.get(str(booking.get("id")))

        if result and booking.get("status") == "PENDING":
            booking["status"] = result.get("status", "PENDING")
            booking["reason"] = result.get("reason", "")
            booking["alternatives"] = result.get("alternatives", [])
            booking["waiting_time"] = result.get("waiting_time", 0)
            booking["turnaround_time"] = result.get("turnaround_time", 0)
            booking["algorithm"] = algorithm

    save_json(BOOKING_FILE, bookings)

    print("\n--- C Module Scheduling Results ---")
    show_bookings([
        booking for booking in bookings
        if str(booking.get("id")) in results
    ])
def admin_menu(fullname):
    while True:
        print(f"\n========== ADMIN MENU | {fullname} ==========")
        print("1. View registered users")
        print("2. Add classroom")
        print("3. View classrooms")
        print("4. View all bookings")
        print("5. Select scheduling algorithm")
        print("6. Process pending bookings")
        print("7. Add timetable entry")
        print("8. View timetable")
        print("9. Logout")

        choice = input("Choose an option: ").strip()

        if choice == "1":
            users = load_users()

            if not users:
                print("No registered users.")

            for user in users:
                print(
                    f"Name: {user.get('fullname')} | "
                    f"Role: {user.get('role', '').title()}"
                )

        elif choice == "2":
            add_room()

        elif choice == "3":
            print_rooms()

        elif choice == "4":
            show_bookings()

        elif choice == "5":
            select_algorithm()

        elif choice == "6":
            process_pending()

        elif choice == "7":
            add_timetable_entry()

        elif choice == "8":
            view_timetable()

        elif choice == "9":
            print("Logged out.")
            return

        else:
            print("Invalid choice. Try again.")
def faculty_menu(fullname):
    while True:
        print(f"\n========== FACULTY MENU | {fullname} ==========")
        print("1. View classrooms")
        print("2. Check/request classroom booking")
        print("3. View my bookings")
        print("4. View timetable")
        print("5. View account details")
        print("6. Logout")

        choice = input("Choose an option: ").strip()

        if choice == "1":
            print_rooms()

        elif choice == "2":
            request_booking(fullname)

        elif choice == "3":
            faculty_bookings(fullname)

        elif choice == "4":
            view_timetable()

        elif choice == "5":
            print("\nAccount Details")
            print("Full Name:", fullname)
            print("Role: Faculty")

        elif choice == "6":
            print("Logged out.")
            return

        else:
            print("Invalid choice. Try again.")

def login():
    role = choose_role("LOGIN")

    if role is None:
        return

    users = load_users()

    print(f"\n========== {role.upper()} LOGIN ==========")

    if role == "admin":
        user = next(
            (u for u in users if u.get("role") == "admin"),
            None
        )

        if user is None:
            print("No Admin account exists. Please sign up first.")
            return

        password = input("Enter Admin password: ")

    else:
        fullname = input("Enter your full name: ").strip()
        password = input("Enter password: ")

        user = next(
            (
                u for u in users
                if u.get("fullname", "").casefold() == fullname.casefold()
                and u.get("role") == "faculty"
            ),
            None
        )

        if user is None:
            print("Faculty account not found. Please sign up first.")
            return

    if not verify_password(
        password,
        user["salt"],
        user["password_hash"]
    ):
        print("Incorrect password.")
        return

    print(f"Login successful! Welcome, {user['fullname']}.")

    if role == "admin":
        admin_menu(user["fullname"])
    else:
        faculty_menu(user["fullname"])

def main():
    print("CampusResOS Terminal Application")

    while True:
        print("\n========== CampusResOS ==========")
        print("1. Sign Up")
        print("2. Login")
        print("3. Exit")

        choice = input("Choose an option: ").strip()

        if choice == "1":
            signup()
        elif choice == "2":
            login()
        elif choice == "3":
            print("Exiting CampusResOS.")
            break
        else:
            print("Invalid choice. Try again.")

if __name__ == "__main__":
    main()