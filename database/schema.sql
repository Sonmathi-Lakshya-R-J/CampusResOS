CREATE DATABASE IF NOT EXISTS campusresos
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE campusresos;

CREATE TABLE IF NOT EXISTS programs (
  program_id INT AUTO_INCREMENT PRIMARY KEY,
  program_code VARCHAR(20) NOT NULL UNIQUE,
  program_name VARCHAR(120) NOT NULL,
  department VARCHAR(120) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS users (
  user_id INT AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(120) NOT NULL,
  email VARCHAR(190) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('ADMIN','FACULTY') NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS faculty (
  faculty_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL UNIQUE,
  employee_code VARCHAR(30) NOT NULL UNIQUE,
  department VARCHAR(120) NOT NULL,
  CONSTRAINT fk_faculty_user FOREIGN KEY (user_id) REFERENCES users(user_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sections (
  section_id INT AUTO_INCREMENT PRIMARY KEY,
  program_id INT NOT NULL,
  section_name VARCHAR(30) NOT NULL,
  academic_year VARCHAR(9) NOT NULL,
  semester TINYINT NOT NULL,
  CONSTRAINT fk_sections_program FOREIGN KEY (program_id) REFERENCES programs(program_id),
  CONSTRAINT uq_section UNIQUE (program_id, section_name, academic_year, semester),
  CONSTRAINT chk_semester CHECK (semester BETWEEN 1 AND 12)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS subjects (
  subject_id INT AUTO_INCREMENT PRIMARY KEY,
  subject_code VARCHAR(20) NOT NULL UNIQUE,
  subject_name VARCHAR(150) NOT NULL,
  credits TINYINT NOT NULL DEFAULT 3,
  CONSTRAINT chk_subject_credits CHECK (credits BETWEEN 0 AND 10)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS classrooms (
  classroom_id INT AUTO_INCREMENT PRIMARY KEY,
  room_code VARCHAR(30) NOT NULL UNIQUE,
  room_name VARCHAR(100) NOT NULL,
  capacity INT NOT NULL,
  room_type ENUM('LECTURE','LAB','SEMINAR','OTHER') NOT NULL DEFAULT 'LECTURE',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT chk_room_capacity CHECK (capacity > 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS time_slots (
  time_slot_id INT AUTO_INCREMENT PRIMARY KEY,
  slot_name VARCHAR(40) NOT NULL UNIQUE,
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  CONSTRAINT chk_slot_times CHECK (start_time < end_time)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS timetables (
  timetable_id INT AUTO_INCREMENT PRIMARY KEY,
  section_id INT NOT NULL,
  academic_year VARCHAR(9) NOT NULL,
  version_no INT NOT NULL DEFAULT 1,
  status ENUM('DRAFT','PUBLISHED','ARCHIVED') NOT NULL DEFAULT 'DRAFT',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_timetables_section FOREIGN KEY (section_id) REFERENCES sections(section_id),
  CONSTRAINT uq_timetable_version UNIQUE (section_id, academic_year, version_no)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS timetable_entries (
  timetable_entry_id INT AUTO_INCREMENT PRIMARY KEY,
  timetable_id INT NOT NULL,
  subject_id INT NOT NULL,
  faculty_id INT NOT NULL,
  classroom_id INT NOT NULL,
  time_slot_id INT NOT NULL,
  day_of_week TINYINT NOT NULL,
  CONSTRAINT fk_entry_timetable FOREIGN KEY (timetable_id) REFERENCES timetables(timetable_id),
  CONSTRAINT fk_entry_subject FOREIGN KEY (subject_id) REFERENCES subjects(subject_id),
  CONSTRAINT fk_entry_faculty FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id),
  CONSTRAINT fk_entry_room FOREIGN KEY (classroom_id) REFERENCES classrooms(classroom_id),
  CONSTRAINT fk_entry_slot FOREIGN KEY (time_slot_id) REFERENCES time_slots(time_slot_id),
  CONSTRAINT chk_day_of_week CHECK (day_of_week BETWEEN 1 AND 7),
  INDEX idx_entry_room_day_slot (classroom_id, day_of_week, time_slot_id),
  INDEX idx_entry_faculty_day_slot (faculty_id, day_of_week, time_slot_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS booking_requests (
  request_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  requester_user_id INT NOT NULL,
  classroom_id INT NOT NULL,
  requested_date DATE NOT NULL,
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  purpose VARCHAR(255) NOT NULL,
  request_type ENUM('ONE_TIME','PERMANENT_CHANGE') NOT NULL DEFAULT 'ONE_TIME',
  status ENUM('PENDING','APPROVED','REJECTED','CANCELLED') NOT NULL DEFAULT 'PENDING',
  reviewed_by INT NULL,
  review_note VARCHAR(500) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_request_user FOREIGN KEY (requester_user_id) REFERENCES users(user_id),
  CONSTRAINT fk_request_room FOREIGN KEY (classroom_id) REFERENCES classrooms(classroom_id),
  CONSTRAINT fk_request_reviewer FOREIGN KEY (reviewed_by) REFERENCES users(user_id),
  CONSTRAINT chk_request_time CHECK (start_time < end_time),
  INDEX idx_request_room_date_status (classroom_id, requested_date, status)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS bookings (
  booking_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  request_id BIGINT NULL UNIQUE,
  requester_user_id INT NOT NULL,
  classroom_id INT NOT NULL,
  booking_date DATE NOT NULL,
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  purpose VARCHAR(255) NOT NULL,
  status ENUM('CONFIRMED','CANCELLED') NOT NULL DEFAULT 'CONFIRMED',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_booking_request FOREIGN KEY (request_id) REFERENCES booking_requests(request_id),
  CONSTRAINT fk_booking_user FOREIGN KEY (requester_user_id) REFERENCES users(user_id),
  CONSTRAINT fk_booking_room FOREIGN KEY (classroom_id) REFERENCES classrooms(classroom_id),
  CONSTRAINT chk_booking_time CHECK (start_time < end_time),
  INDEX idx_booking_room_date_status (classroom_id, booking_date, status, start_time, end_time),
  INDEX idx_booking_user_date (requester_user_id, booking_date)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS booking_history (
  history_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  booking_id BIGINT NULL,
  request_id BIGINT NULL,
  actor_user_id INT NOT NULL,
  action VARCHAR(60) NOT NULL,
  details JSON NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_history_booking FOREIGN KEY (booking_id) REFERENCES bookings(booking_id),
  CONSTRAINT fk_history_request FOREIGN KEY (request_id) REFERENCES booking_requests(request_id),
  CONSTRAINT fk_history_actor FOREIGN KEY (actor_user_id) REFERENCES users(user_id),
  INDEX idx_history_booking_time (booking_id, created_at)
) ENGINE=InnoDB;
