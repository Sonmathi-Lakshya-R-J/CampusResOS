<!-- <div align="center">

# CampusResOS

### Integrated Timetable, Classroom Booking & Resource Management System

<p>
  A web-based academic resource management system that combines
  <strong>Operating Systems</strong>, <strong>DBMS</strong>, and
  <strong>Web Development</strong> concepts.
</p>

<!-- <p>
  <a href="https://github.com/Sonmathi-Lakshya-R-J/CampusResOS">
    <img src="https://img.shields.io/badge/GitHub-CampusResOS-black?logo=github" alt="GitHub">
  </a>
  <img src="https://img.shields.io/badge/Status-In%20Development-blue" alt="Status">
  <img src="https://img.shields.io/badge/Project-Academic-orange" alt="Academic Project">
</p> -->

<!-- </div>

--- --> -->

# CampusResOS

### Integrated Timetable, Classroom Booking & Resource Management System

CampusResOS is a web-based classroom and timetable resource management system designed for educational institutions. It helps administrators manage classrooms, faculty, timetables, conflicts, and booking requests, while allowing faculty members to view schedules, find available classrooms, and submit booking requests.

The project combines **Operating System and DBMS concepts** with a practical classroom resource-management problem, including scheduling algorithms, concurrency, synchronization, resource allocation, and a normalized MySQL database.


## 📑 Table of Contents

- [About the Project](#-about-the-project)
- [Problem Statement](#-problem-statement)
- [Objectives](#-objectives)
- [Team Members](#-team-members)
- [Technologies and Tools](#-technologies-and-tools)
- [System Architecture](#-system-architecture)
- [Major Features and Modules](#-major-features-and-modules)
- [Project Workflow](#-project-workflow)
- [Database Design](#-database-design)
- [Operating System Concepts](#-operating-system-concepts)
- [Project Setup](#-project-setup)
- [Database Setup](#-database-setup)
- [Configuration](#-configuration)
- [Running the Project](#-running-the-project)
- [Project Structure](#-project-structure)
- [Current Project Status](#-current-project-status)
- [Roadmap](#-roadmap)
- [Known Issues](#-known-issues)
- [Future Scope](#-future-scope)
- [Contributing](#-contributing)
- [License](#-license)
- [Team](#-team)

---

## 📌 About the Project

CampusResOS is a web-based classroom and timetable resource management system designed for educational institutions.

The system provides a centralized platform for administrators and faculty members to manage classrooms, faculty information, timetables, classroom availability, conflicts, and booking requests.

### 👨‍💼 Admin

Administrators can:

- Manage classrooms and resources
- Manage faculty information
- Upload and manage timetable data
- Detect timetable conflicts
- Review classroom booking requests
- Monitor classroom availability
- View system statistics and reports

### 👩‍🏫 Faculty

Faculty members can:

- View their timetable
- Search for available classrooms
- Check free time slots
- Submit classroom booking requests
- Track booking request status
- View booking history

> **[!NOTE]**
> CampusResOS is designed as an academic project to demonstrate Operating System and DBMS concepts through a practical classroom resource-management problem.

---

## 🎯 Problem Statement

Managing classroom timetables and room allocation manually can result in:

- Classroom clashes
- Faculty scheduling conflicts
- Incorrect classroom allocation
- Classroom capacity violations
- Difficulty identifying available classrooms
- Conflicts between simultaneous booking requests
- Manual handling of temporary and permanent booking requests

CampusResOS aims to provide a unified system that detects scheduling conflicts, manages classroom resources, processes booking requests, and demonstrates OS and DBMS concepts through practical implementation.

---

## 🎯 Objectives

The primary objectives of CampusResOS are to:

1. Detect classroom and faculty timetable conflicts.
2. Identify classroom capacity violations.
3. Provide dynamic classroom allocation.
4. Allow faculty to request temporary or permanent classroom bookings.
5. Process concurrent booking requests safely.
6. Implement FCFS, SJF, and Priority Scheduling.
7. Demonstrate processes, threads, synchronization, and IPC.
8. Detect unsafe resource-allocation states and potential deadlocks.
9. Maintain a normalized MySQL database up to 3NF.
10. Demonstrate transactions, concurrency control, locking, and commit/rollback.
11. Maintain booking and event history.
12. Compare scheduling algorithms using performance metrics.

---

## 👥 Team Members

| Member | Role | Responsibilities |
|---|---|---|
| **Sonmathi Lakshya R J** | Database & DBMS Lead | MySQL database, ER model, 3NF schema, datasets, constraints, queries, transactions, database integration |
| **Vaibhavi** | OS & Admin Module Lead | OS scheduling algorithms, C/POSIX module, synchronization, resource allocation, Admin module |
| **Priya Kimothi** | Faculty & Flask Integration Lead | Flask backend integration, Faculty module, booking workflow, API integration and testing |

### Team Information

**Team ID:** `OSDBMS-V-2026-T041`

---

## 🛠️ Technologies and Tools

### Programming Languages

- **C** — Operating System and scheduling module
- **Python** — Backend development
- **HTML** — Frontend structure
- **CSS** — Frontend styling
- **JavaScript** — Frontend functionality
- **SQL** — Database operations

### Frameworks and Technologies

- **Flask** — Backend and REST API
- **C/POSIX** — Processes, threads, synchronization, and IPC
- **MySQL** — Relational database

### Operating System Concepts

- Processes
- Threads
- FCFS Scheduling
- SJF Scheduling
- Priority Scheduling
- Mutexes
- Semaphores
- Inter-Process Communication (IPC)
- Resource Allocation
- Context Switching
- Deadlock Detection

### DBMS Concepts

- ER Modeling
- Normalization up to 3NF
- Primary Keys
- Foreign Keys
- Constraints
- Indexing
- Views
- Triggers
- Transactions
- ACID Properties
- Concurrency Control
- Database Locking
- Commit/Rollback

### Development Tools

- Git
- GitHub
- Visual Studio Code
- MySQL Workbench
- Postman / API Testing Tool

---

## 🏗️ System Architecture

```text
                         CampusResOS
                              |
                 +------------+------------+
                 |                         |
               Admin                    Faculty
                 |                         |
                 +------------+------------+
                              |
                       Web Interface
                              |
                       Flask Backend
                              |
                 +------------+------------+
                 |                         |
                 ↓                         ↓
          MySQL Database              C/POSIX Module
                 |                         |
        +--------+--------+        +-------+--------+
        |        |        |        |       |        |
      Users  Classrooms  Bookings  Scheduling  Synchronization
        |        |        |        Processes    IPC
     Faculty Timetable History     Threads   Deadlock Detection
```

---

## 🚀 Major Features and Modules

### 1. Authentication and Role Management

The system provides separate access for:

- Admin
- Faculty

Each role receives access to functionality relevant to that role.

### 2. Timetable Management

The Admin can upload and manage timetable information.

The system validates timetable data and checks for:

- Classroom clashes
- Faculty clashes
- Capacity violations
- Invalid combined-class allocations

### 3. Classroom Management

The Admin can manage classroom information such as:

- Room ID
- Room name
- Capacity
- Room type
- Availability

### 4. Faculty Management

The Admin can manage faculty information and associate faculty members with timetable entries and booking requests.

### 5. Conflict Detection

CampusResOS identifies scheduling conflicts automatically.

#### Classroom Conflict

```text
Room C101
10:00 - 11:00 → Class A
10:00 - 11:00 → Class B

Result: Classroom Conflict
```

#### Faculty Conflict

```text
Faculty X
10:00 - 11:00 → Class A
10:00 - 11:00 → Class B

Result: Faculty Conflict
```

#### Capacity Violation

```text
Students: 70
Room Capacity: 50

Result: Capacity Violation
```

### 6. Free Slot and Classroom Availability

Faculty can select a classroom and check its available time slots.

The system considers existing timetable entries and bookings before displaying available slots.

### 7. Classroom Booking

Faculty can submit classroom booking requests.

The system supports:

- One-time bookings
- Temporary bookings
- Permanent/recurring booking requests

Each request is validated before allocation.

### 8. OS-Based Scheduling

Each booking request can be treated as a process competing for limited resources.

CampusResOS implements:

- **FCFS** — First-Come, First-Served
- **SJF** — Shortest Job First
- **Priority Scheduling** — Requests are processed according to their assigned priority

Scheduling performance can be evaluated using:

- Waiting Time
- Turnaround Time
- Throughput
- Resource Utilization
- Conflict Rate

### 9. Concurrent Booking

The system demonstrates multiple users attempting to reserve the same classroom simultaneously.

OS synchronization mechanisms such as:

- Threads
- Mutexes
- Semaphores

are used to control concurrent access.

Database transactions and locking are used to maintain consistent booking information.

### 10. Deadlock Detection

Resource conflicts can be analyzed using:

- Resource Allocation Graph (RAG)
- Banker-style deadlock detection approach

Possible resources include:

- Classrooms
- Faculty
- Time slots

### 11. Booking History

The system maintains records of booking requests and completed bookings.

Administrators can review:

- Previous bookings
- Request status
- Allocated rooms
- Booking dates and times
- Historical activity

### 12. Scheduling Analytics

Scheduling algorithms can be compared using:

```text
Waiting Time
Turnaround Time
Throughput
Resource Utilization
Conflict Rate
```

Results can be presented through tables and dashboard reports.

---

## 🔄 Project Workflow

```text
              Admin / Faculty
                     |
                     ↓
              Web Interface
                     |
                     ↓
              Flask Backend
                     |
            +--------+--------+
            |                 |
            ↓                 ↓
       MySQL Database    C/POSIX Module
            |                 |
       User & Resource    Scheduling
       Management         Synchronization
       Bookings           Resource Allocation
       History            Deadlock Detection
            |                 |
            +--------+--------+
                     |
                     ↓
              Booking Result
                     |
                     ↓
             Database / History
```

---

## 🗄️ Database Design

The database is designed using an **Entity-Relationship (ER) model** and normalized up to **Third Normal Form (3NF)**.

### Core Entities

```text
Users
Faculty
Classrooms
Subjects
Timetable
Booking_Requests
Bookings
Booking_History
```

### Example Relationship

```text
Faculty
   |
   | submits
   ↓
Booking_Request
   |
   | results in
   ↓
Booking
   |
   | uses
   ↓
Classroom
```

The database uses:

- Primary Keys
- Foreign Keys
- Constraints
- Relationships
- Indexes
- Views
- Triggers
- Transactions
- Database Locking

---

## ⚙️ Operating System Concepts

CampusResOS demonstrates OS concepts through the classroom booking and resource-allocation workflow.

| Concept | Application in CampusResOS |
|---|---|
| Processes | Represent scheduling/booking tasks |
| Threads | Handle concurrent operations |
| FCFS | Process requests according to arrival order |
| SJF | Process requests based on job length |
| Priority Scheduling | Process requests according to priority |
| Mutex | Protect shared resources |
| Semaphore | Control access to limited resources |
| IPC | Communication between Flask and the C/POSIX module |
| Resource Allocation | Manage classrooms, faculty, and time slots |
| Context Switching | Demonstrated as part of process scheduling |
| Deadlock Detection | Identify unsafe resource-allocation conditions |

---

## ⚙️ Project Setup

### Prerequisites

Install the following before running CampusResOS:

- Python
- MySQL
- GCC/MinGW or another compatible C compiler
- Git
- Visual Studio Code
- Postman or another API testing tool

### 1. Clone the Repository

```bash
git clone https://github.com/Sonmathi-Lakshya-R-J/CampusResOS.git
cd CampusResOS
```

### 2. Create a Python Virtual Environment

#### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

#### Linux/macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

If `requirements.txt` has not yet been created:

```bash
pip install flask mysql-connector-python
```

> **[!WARNING]**
> Use the dependency versions defined by the project when `requirements.txt` is available.

---

## 🗃️ Database Setup

### 1. Start MySQL

Make sure the MySQL server is running.

### 2. Create the Database

Open MySQL:

```bash
mysql -u root -p
```

Create the database:

```sql
CREATE DATABASE campusresos;
```

Select it:

```sql
USE campusresos;
```

### 3. Import the Database Schema

```bash
mysql -u root -p campusresos < database/schema.sql
```

### 4. Import Sample Data

```bash
mysql -u root -p campusresos < database/sample_data.sql
```

> **[!NOTE]**
> Update the SQL file names if the actual project structure uses different filenames.

---

## 🔐 Configuration

Create a `.env` file in the backend directory:

```env
DB_HOST=localhost
DB_PORT=3306
DB_NAME=campusresos
DB_USER=root
DB_PASSWORD=[YOUR_MYSQL_PASSWORD]

FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=[YOUR_SECRET_KEY]
```

Never commit passwords, API keys, or other sensitive information to GitHub.

Add the following to `.gitignore`:

```gitignore
.env
venv/
__pycache__/
*.pyc
```

> **[!WARNING]**
> Do not upload `.env` files containing real credentials to the repository.

---

## ▶️ Running the Project

### Start the Flask Backend

```bash
cd backend
python app.py
```

The development server should be available at:

```text
http://127.0.0.1:5000
```

### Run the OS Module

Navigate to the OS module:

```bash
cd os_module
```

Compile the C program:

```bash
gcc scheduler.c -o scheduler
```

Run it:

```bash
./scheduler
```

#### Windows / MinGW

```bash
scheduler.exe
```

> **[!NOTE]**
> Exact compilation commands may vary depending on the C/POSIX features and compiler environment used by the team.

---

## 📁 Project Structure

```text
CampusResOS/
│
├── backend/
│   ├── app.py
│   ├── routes/
│   ├── models/
│   ├── services/
│   └── config/
│
├── frontend/
│   ├── admin/
│   ├── faculty/
│   ├── css/
│   └── js/
│
├── os_module/
│   ├── fcfs.c
│   ├── sjf.c
│   ├── priority.c
│   ├── scheduler.c
│   └── synchronization.c
│
├── database/
│   ├── schema.sql
│   ├── sample_data.sql
│   └── queries.sql
│
├── docs/
│   ├── ER_Diagram/
│   ├── Architecture/
│   └── Screenshots/
│
├── requirements.txt
├── .gitignore
└── README.md
```

> **[!NOTE]**
> The structure above represents the planned project organization and should be updated as the repository develops.

---

## 📊 Current Project Status

**Development Phase:** Active Development / MVP Development

### Progress

- [x] Project concept and problem definition
- [x] Project architecture
- [x] Technology stack selection
- [x] Team responsibility allocation
- [x] Initial project proposal
- [x] Admin and Faculty workflow planning
- [x] Database design planning
- [x] OS scheduling approach planning
- [ ] MySQL database implementation
- [ ] Sample dataset preparation
- [ ] Flask backend integration
- [ ] Admin module
- [ ] Faculty module
- [ ] Timetable conflict detection
- [ ] Classroom availability module
- [ ] Booking system
- [ ] FCFS implementation
- [ ] SJF implementation
- [ ] Priority Scheduling implementation
- [ ] Thread synchronization
- [ ] Mutex/Semaphore implementation
- [ ] IPC integration
- [ ] Deadlock detection
- [ ] Analytics dashboard
- [ ] Full system integration
- [ ] Final testing
- [ ] Final documentation

---

## 🗺️ Roadmap

### Phase 1 — Foundation

- Finalize database schema
- Create sample datasets
- Implement basic Flask backend
- Implement standalone OS scheduling algorithms

### Phase 2 — Core System

- Build Admin module
- Build Faculty module
- Implement timetable management
- Implement conflict detection
- Implement classroom availability
- Implement booking requests

### Phase 3 — OS + DBMS Integration

- Connect booking requests with scheduling algorithms
- Implement concurrent booking
- Add mutex/semaphore synchronization
- Implement IPC between Flask and C/POSIX module
- Add database transactions and locking
- Implement deadlock detection

### Phase 4 — Analytics and Testing

- Calculate scheduling metrics
- Build simple analytics dashboard
- Test concurrent requests
- Test conflict detection
- Test database constraints
- Perform integration testing

### Phase 5 — Finalization

- UI refinement
- Bug fixing
- Documentation
- Screenshots
- Final presentation
- Final demonstration

---

## ⚠️ Known Issues

The following areas are currently under development:

- Flask and C/POSIX integration
- Concurrent booking implementation
- Database integration
- Frontend development
- Deadlock detection
- Analytics implementation

This section will be updated as development progresses.

---

## 🔮 Future Scope

Potential future improvements include:

- Advanced timetable generation
- Automated classroom recommendation
- Equipment/resource management
- Additional scheduling algorithms
- Enhanced analytics
- Notification system
- Mobile-friendly interface
- Integration with existing university management systems
- Automated timetable optimization

---

## 🤝 Contributing

CampusResOS is currently developed as an academic team project.

For team development, use feature branches and review changes before merging.

### 1. Create a Branch

```bash
git checkout -b feature/[feature-name]
```

### 2. Make Your Changes

Implement and test the required feature.

### 3. Stage the Changes

```bash
git add .
```

### 4. Commit

```bash
git commit -m "Add [feature-name]"
```

### 5. Push the Branch

```bash
git push origin feature/[feature-name]
```

### 6. Create a Pull Request

Create a Pull Request on GitHub and have another team member review the changes before merging.

---

## 📜 License

This project is developed for academic purposes as part of a B.Tech OSDBMS project.

**License:** To Be Decided

> **[!NOTE]**
> Update this section once the project team decides on the repository license.

---

## 👩‍💻 Team

### CampusResOS

**Team ID:** `OSDBMS-V-2026-T041`

Built as an academic project integrating:

**Operating Systems + Database Management Systems + Web Development**

---

<div align="center">

### ⭐ CampusResOS

*Managing classrooms smarter through OS, DBMS, and web technologies.*

</div>
