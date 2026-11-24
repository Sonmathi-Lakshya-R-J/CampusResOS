import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from werkzeug.security import generate_password_hash
from db import get_connection

def main():
    conn = get_connection()
    cur = conn.cursor()
    try:
        users = [
            ("CampusResOS Admin", "admin@gmail.com", generate_password_hash("Campus@123"), "ADMIN"),
            ("Demo Faculty", "faculty@gmail.com", generate_password_hash("Campus@123"), "FACULTY"),
        ]
        for row in users:
            cur.execute("""
                INSERT INTO users (full_name,email,password_hash,role)
                VALUES (%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE full_name=VALUES(full_name), password_hash=VALUES(password_hash), role=VALUES(role)
            """, row)

        cur.execute("""
            INSERT INTO programs (program_code,program_name,department)
            VALUES ('BTECH-CSE','B.Tech Computer Science and Engineering','Computer Science')
            ON DUPLICATE KEY UPDATE program_name=VALUES(program_name)
        """)
        cur.execute("""
            INSERT INTO sections (program_id,section_name,academic_year,semester)
            SELECT program_id,'CSE-A','2026-2027',5 FROM programs WHERE program_code='BTECH-CSE'
            ON DUPLICATE KEY UPDATE section_name=VALUES(section_name)
        """)
        for code, name, credits in [
            ("CSE301","Principles of Computer System Design",3),
            ("CSE302","Database Management Systems",4),
            ("CSE303","Operating Systems",4),
        ]:
            cur.execute("""
                INSERT INTO subjects (subject_code,subject_name,credits)
                VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE subject_name=VALUES(subject_name)
            """, (code,name,credits))
        for code, name, capacity, room_type in [
            ("CR-101","Lecture Room 101",60,"LECTURE"),
            ("CR-102","Lecture Room 102",40,"LECTURE"),
            ("LAB-201","Computer Lab 201",35,"LAB"),
            ("SEM-301","Seminar Hall 301",80,"SEMINAR"),
        ]:
            cur.execute("""
                INSERT INTO classrooms (room_code,room_name,capacity,room_type)
                VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE room_name=VALUES(room_name), capacity=VALUES(capacity)
            """, (code,name,capacity,room_type))
        for name, start, end in [
            ("Slot 1","09:00:00","10:00:00"),
            ("Slot 2","10:00:00","11:00:00"),
            ("Slot 3","11:15:00","12:15:00"),
            ("Slot 4","13:00:00","14:00:00"),
            ("Slot 5","14:00:00","15:00:00"),
        ]:
            cur.execute("""
                INSERT INTO time_slots (slot_name,start_time,end_time) VALUES (%s,%s,%s)
                ON DUPLICATE KEY UPDATE start_time=VALUES(start_time), end_time=VALUES(end_time)
            """, (name,start,end))

        cur.execute("""
            INSERT INTO faculty (user_id,employee_code,department)
            SELECT user_id,'FAC-DEMO-01','Computer Science'
            FROM users WHERE email='faculty@gmail.com'
            ON DUPLICATE KEY UPDATE department=VALUES(department)
        """)
        conn.commit()
        print("Demo data ready. Demo password for both accounts: Campus@123")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
