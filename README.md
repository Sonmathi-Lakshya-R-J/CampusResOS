# CampusResOS — Integrated OS + DBMS Project

CampusResOS manages classroom timetables, temporary and recurring extra-class bookings, timetable-change requests, and OS scheduling demonstrations. Stack: Flask/Python, MySQL 8, HTML/CSS/JavaScript, C/POSIX, pthreads, Unix-domain socket IPC.

## Features
- Admin and faculty roles with database-driven login.
- Room availability validation, explicit one-time booking confirmation, date-scoped MySQL advisory locks and transactions.
- Recurring booking preview and confirmation APIs; conflicting dates are presented and the faculty may choose to proceed only with available dates.
- Existing timetable-change request workflow plus schema support for effective-dated change details.
- C worker demonstrates FCFS, SJF and Priority scheduling with multithreaded socket clients, mutex-protected metrics, waiting/turnaround and throughput calculations.
- OS educational endpoint for deadlock-cycle detection and prevention explanation; it never deadlocks live resources.
- Additive migration defines recurring occurrences, OS metrics, deadlock demo records, views, triggers and stored procedures.

## Requirements
- Python 3.10+
- MySQL 8.0+
- GCC and POSIX pthreads (Ubuntu/WSL or macOS)

## Setup (fresh database)
1. Create a MySQL database/user and configure environment variables from `.env.example`.
2. Run `mysql -u root -p < database/schema.sql`.
3. Run `mysql -u root -p campusresos < database/migrations/001_campusresos_features.sql`.
4. Install Python dependencies: `python -m pip install -r backend/requirements.txt`.
5. Seed demo data: `python backend/seed_demo.py`. Demo accounts: `admin@campusresos.local` and `faculty@campusresos.local`, password `Campus@123`. Change these credentials before any non-demo use.
6. Build/start the C worker in one terminal: `cd os_module && make && ./campusresos_worker`.
7. Start Flask in another terminal: `python backend/run.py`. Open `http://127.0.0.1:5000`.

## Existing database
Back up first. Do **not** rerun `database/schema.sql` against an existing installation as a substitute for migration. The additive migration is intended to add new objects without dropping tables, but review it against your MySQL version and current schema before running.

## Recurring booking API
- `POST /api/recurring-bookings/preview`: `{classroom_id,start_date,weeks,start_time,end_time,purpose}`
- `POST /api/recurring-bookings/confirm`: send the same booking details plus `dates` from preview and `allow_gaps: true` only after faculty explicitly accepts partial availability.

## OS + DBMS mapping
- OS: process/job lifecycle, FCFS/SJF/Priority algorithms, multithreaded workers, mutex synchronization, IPC, resource allocation, deadlock cycle simulation/prevention, starvation-aging policy documentation and scheduler metrics.
- DBMS: relational design/3NF, PK/FK/CHECK constraints, indexes, transactions, locking, triggers, views, stored procedures, audit history.

## Scope notes
- Priority scheduling currently remains an educational scheduler interface; full production-grade priority dispatch of real pending booking jobs is a further integration milestone.
- Effective-dated timetable change schema is provided; approval application needs the exact timetable change policy finalized and tested against the university's timetable format.
- The sample timetable images should be transcribed to CSV/XLSX and validated before import; this package does not claim OCR-perfect timetable ingestion.
