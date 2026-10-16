CREATE DATABASE IF NOT EXISTS campusresos_new;
USE campusresos_new;

CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('ADMIN', 'FACULTY') NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_users_name_role (full_name, role)
);

CREATE TABLE IF NOT EXISTS faculty (
    faculty_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    employee_code VARCHAR(50) NOT NULL UNIQUE,
    department VARCHAR(120) NOT NULL,
    designation VARCHAR(120) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS classrooms (
    classroom_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    room_code VARCHAR(40) NOT NULL UNIQUE,
    room_name VARCHAR(120) NOT NULL,
    building VARCHAR(120) NOT NULL,
    floor_no INT NOT NULL DEFAULT 0,
    room_type ENUM(
        'CLASSROOM',
        'LECTURE_THEATRE',
        'LAB',
        'SEMINAR_HALL',
        'OTHER'
    ) NOT NULL DEFAULT 'CLASSROOM',
    capacity INT NOT NULL,
    status ENUM('AVAILABLE', 'MAINTENANCE', 'INACTIVE') NOT NULL DEFAULT 'AVAILABLE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (capacity > 0)
);

CREATE TABLE IF NOT EXISTS booking_requests (
    request_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    faculty_id BIGINT NOT NULL,
    requested_classroom_id BIGINT NOT NULL,
    requested_date DATE NOT NULL,
    recurrence_end_date DATE NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    required_capacity INT NOT NULL,
    priority INT NOT NULL DEFAULT 5,
    booking_type ENUM('TEMPORARY', 'PERMANENT') NOT NULL DEFAULT 'TEMPORARY',
    status ENUM('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED') NOT NULL DEFAULT 'PENDING',
    reason VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id),
    FOREIGN KEY (requested_classroom_id) REFERENCES classrooms(classroom_id),
    CHECK (required_capacity > 0),
    CHECK (priority BETWEEN 1 AND 10),
    CHECK (end_time > start_time),
    CHECK (recurrence_end_date IS NULL OR recurrence_end_date >= requested_date),
    INDEX idx_request_status (status),
    INDEX idx_request_dates (requested_date, recurrence_end_date)
);

CREATE TABLE IF NOT EXISTS booking_request_days (
    request_day_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    request_id BIGINT NOT NULL,
    day_of_week ENUM(
        'MONDAY',
        'TUESDAY',
        'WEDNESDAY',
        'THURSDAY',
        'FRIDAY',
        'SATURDAY',
        'SUNDAY'
    ) NOT NULL,
    FOREIGN KEY (request_id) REFERENCES booking_requests(request_id) ON DELETE CASCADE,
    UNIQUE (request_id, day_of_week)
);

CREATE TABLE IF NOT EXISTS bookings (
    booking_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    request_id BIGINT NOT NULL,
    classroom_id BIGINT NOT NULL,
    faculty_id BIGINT NOT NULL,
    booking_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    status ENUM('CONFIRMED', 'CANCELLED', 'COMPLETED') NOT NULL DEFAULT 'CONFIRMED',
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (request_id) REFERENCES booking_requests(request_id),
    FOREIGN KEY (classroom_id) REFERENCES classrooms(classroom_id),
    FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    CHECK (end_time > start_time),
    INDEX idx_booking_request (request_id),
    INDEX idx_booking_room_date (classroom_id, booking_date),
    INDEX idx_booking_faculty_date (faculty_id, booking_date),
    INDEX idx_booking_status (status)
);

CREATE TABLE IF NOT EXISTS booking_history (
    history_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    booking_id BIGINT NOT NULL,
    action ENUM('CREATED', 'APPROVED', 'REJECTED', 'CANCELLED', 'COMPLETED') NOT NULL,
    performed_by BIGINT NOT NULL,
    notes VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(booking_id),
    FOREIGN KEY (performed_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS programs (
    program_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    program_code VARCHAR(30) NOT NULL UNIQUE,
    program_name VARCHAR(150) NOT NULL,
    degree VARCHAR(80) NOT NULL,
    department VARCHAR(120) NOT NULL
);

CREATE TABLE IF NOT EXISTS sections (
    section_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    program_id BIGINT NOT NULL,
    academic_year VARCHAR(20) NOT NULL,
    year_level INT NOT NULL,
    semester INT NOT NULL,
    section_name VARCHAR(30) NOT NULL,
    student_count INT NOT NULL DEFAULT 0,
    FOREIGN KEY (program_id) REFERENCES programs(program_id),
    CHECK (year_level BETWEEN 1 AND 6),
    CHECK (semester BETWEEN 1 AND 12),
    CHECK (student_count >= 0),
    UNIQUE (program_id, academic_year, semester, section_name)
);

CREATE TABLE IF NOT EXISTS subjects (
    subject_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    program_id BIGINT NOT NULL,
    subject_code VARCHAR(30) NOT NULL UNIQUE,
    subject_name VARCHAR(150) NOT NULL,
    subject_type ENUM('THEORY', 'LAB', 'ELECTIVE', 'AUDIT', 'OTHER') NOT NULL DEFAULT 'THEORY',
    credits DECIMAL(3,1) NOT NULL DEFAULT 3.0,
    FOREIGN KEY (program_id) REFERENCES programs(program_id),
    CHECK (credits >= 0)
);

CREATE TABLE IF NOT EXISTS time_slots (
    slot_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    slot_label VARCHAR(50) NOT NULL UNIQUE,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    slot_order INT NOT NULL UNIQUE,
    CHECK (end_time > start_time)
);

CREATE TABLE IF NOT EXISTS timetables (
    timetable_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    classroom_id BIGINT NOT NULL,
    revision_no INT NOT NULL DEFAULT 1,
    effective_from DATE NOT NULL,
    effective_to DATE NULL,
    status ENUM('DRAFT', 'ACTIVE', 'ARCHIVED') NOT NULL DEFAULT 'DRAFT',
    FOREIGN KEY (classroom_id) REFERENCES classrooms(classroom_id),
    CHECK (revision_no > 0),
    CHECK (effective_to IS NULL OR effective_to >= effective_from),
    UNIQUE (classroom_id, revision_no),
    INDEX idx_timetable_status (status)
);

CREATE TABLE IF NOT EXISTS timetable_entries (
    entry_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timetable_id BIGINT NOT NULL,
    day_of_week ENUM('MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY') NOT NULL,
    slot_id BIGINT NOT NULL,
    section_id BIGINT NOT NULL,
    subject_id BIGINT NULL,
    faculty_id BIGINT NOT NULL,
    activity_type ENUM('THEORY', 'LAB', 'ELECTIVE', 'LUNCH', 'ONLINE', 'TRAINING', 'CEC', 'OTHER') NOT NULL DEFAULT 'THEORY',
    activity_name VARCHAR(150),
    notes VARCHAR(500),
    FOREIGN KEY (timetable_id) REFERENCES timetables(timetable_id) ON DELETE CASCADE,
    FOREIGN KEY (slot_id) REFERENCES time_slots(slot_id),
    FOREIGN KEY (section_id) REFERENCES sections(section_id),
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id),
    FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id),
    UNIQUE (timetable_id, day_of_week, slot_id),
    INDEX idx_entry_faculty (faculty_id),
    INDEX idx_entry_section (section_id)
);

CREATE TABLE IF NOT EXISTS app_settings (
    setting_key VARCHAR(100) PRIMARY KEY,
    setting_value VARCHAR(255) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

INSERT INTO app_settings (setting_key, setting_value)
VALUES ('scheduling_algorithm', 'FCFS')
ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value);

INSERT INTO classrooms
    (room_code, room_name, building, floor_no, room_type, capacity, status)
VALUES
    ('LT1', 'LT1', 'Main Academic Block', 1, 'LECTURE_THEATRE', 120, 'AVAILABLE'),
    ('LT5', 'LT5', 'Main Academic Block', 1, 'LECTURE_THEATRE', 120, 'AVAILABLE'),
    ('LT8', 'LT8', 'Main Academic Block', 2, 'LECTURE_THEATRE', 100, 'AVAILABLE'),
    ('CR1', 'CR1', 'Academic Block A', 1, 'CLASSROOM', 60, 'AVAILABLE'),
    ('CR8', 'CR8', 'Academic Block A', 2, 'CLASSROOM', 60, 'AVAILABLE'),
    ('NEW LAB 1', 'NEW LAB 1', 'Computer Science Block', 1, 'LAB', 40, 'AVAILABLE')
ON DUPLICATE KEY UPDATE
    room_name = VALUES(room_name),
    building = VALUES(building),
    floor_no = VALUES(floor_no),
    room_type = VALUES(room_type),
    capacity = VALUES(capacity),
    status = VALUES(status);

INSERT INTO programs (program_code, program_name, degree, department)
VALUES ('CSE', 'Computer Science and Engineering', 'B.Tech', 'Computer Science')
ON DUPLICATE KEY UPDATE
    program_name = VALUES(program_name),
    degree = VALUES(degree),
    department = VALUES(department);

INSERT INTO sections
    (program_id, academic_year, year_level, semester, section_name, student_count)
SELECT program_id, '2026-2027', 2, 3, section_list.section_name, 50
FROM programs
CROSS JOIN (
    SELECT 'DS-2' AS section_name
    UNION ALL SELECT 'SEC-A'
    UNION ALL SELECT 'SEC-E'
    UNION ALL SELECT 'SEC-F'
) AS section_list
WHERE program_code = 'CSE'
ON DUPLICATE KEY UPDATE
    student_count = VALUES(student_count);

INSERT INTO subjects (program_id, subject_code, subject_name, subject_type, credits)
SELECT program_id, 'CSE201', 'Data Structures', 'THEORY', 4.0
FROM programs
WHERE program_code = 'CSE'
ON DUPLICATE KEY UPDATE
    subject_name = VALUES(subject_name),
    subject_type = VALUES(subject_type),
    credits = VALUES(credits);

INSERT INTO subjects (program_id, subject_code, subject_name, subject_type, credits)
SELECT program_id, 'CSE202', 'Database Management Systems', 'THEORY', 4.0
FROM programs
WHERE program_code = 'CSE'
ON DUPLICATE KEY UPDATE
    subject_name = VALUES(subject_name),
    subject_type = VALUES(subject_type),
    credits = VALUES(credits);

INSERT INTO subjects (program_id, subject_code, subject_name, subject_type, credits)
SELECT program_id, 'CSE203', 'Operating Systems', 'THEORY', 4.0
FROM programs
WHERE program_code = 'CSE'
ON DUPLICATE KEY UPDATE
    subject_name = VALUES(subject_name),
    subject_type = VALUES(subject_type),
    credits = VALUES(credits);

INSERT INTO subjects (program_id, subject_code, subject_name, subject_type, credits)
SELECT program_id, 'CSE204', 'Computer Networks Lab', 'LAB', 2.0
FROM programs
WHERE program_code = 'CSE'
ON DUPLICATE KEY UPDATE
    subject_name = VALUES(subject_name),
    subject_type = VALUES(subject_type),
    credits = VALUES(credits);

INSERT INTO time_slots (slot_label, start_time, end_time, slot_order)
VALUES
    ('09:00-10:00', '09:00:00', '10:00:00', 1),
    ('10:00-11:00', '10:00:00', '11:00:00', 2),
    ('11:00-12:00', '11:00:00', '12:00:00', 3),
    ('12:00-13:00', '12:00:00', '13:00:00', 4),
    ('14:00-15:00', '14:00:00', '15:00:00', 5),
    ('15:00-16:00', '15:00:00', '16:00:00', 6)
ON DUPLICATE KEY UPDATE
    start_time = VALUES(start_time),
    end_time = VALUES(end_time);