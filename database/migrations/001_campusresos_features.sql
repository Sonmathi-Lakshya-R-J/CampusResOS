-- CampusResOS additive migration for MySQL 8.0+
-- Back up your database before running. Does not drop or reset existing tables.
USE campusresos;
CREATE TABLE IF NOT EXISTS booking_occurrences (
 occurrence_id BIGINT AUTO_INCREMENT PRIMARY KEY,
 request_id BIGINT NOT NULL,
 occurrence_date DATE NOT NULL,
 classroom_id INT NOT NULL,
 start_time TIME NOT NULL,
 end_time TIME NOT NULL,
 status ENUM('PROPOSED','CONFIRMED','CONFLICT','CANCELLED') NOT NULL DEFAULT 'PROPOSED',
 conflict_reason VARCHAR(255) NULL,
 booking_id BIGINT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uq_request_occurrence (request_id, occurrence_date),
 INDEX idx_occurrence_room_date (classroom_id, occurrence_date, status),
 CONSTRAINT fk_occ_request FOREIGN KEY (request_id) REFERENCES booking_requests(request_id),
 CONSTRAINT fk_occ_room FOREIGN KEY (classroom_id) REFERENCES classrooms(classroom_id),
 CONSTRAINT fk_occ_booking FOREIGN KEY (booking_id) REFERENCES bookings(booking_id),
 CONSTRAINT chk_occ_time CHECK (start_time < end_time)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS timetable_change_details (
 change_id BIGINT AUTO_INCREMENT PRIMARY KEY,
 request_id BIGINT NOT NULL UNIQUE,
 timetable_entry_id INT NOT NULL,
 requested_classroom_id INT NULL,
 requested_day_of_week TINYINT NULL,
 requested_time_slot_id INT NULL,
 effective_date DATE NOT NULL,
 change_reason VARCHAR(500) NOT NULL,
 applied_at TIMESTAMP NULL,
 CONSTRAINT fk_change_request FOREIGN KEY (request_id) REFERENCES booking_requests(request_id),
 CONSTRAINT fk_change_entry FOREIGN KEY (timetable_entry_id) REFERENCES timetable_entries(timetable_entry_id),
 CONSTRAINT fk_change_room FOREIGN KEY (requested_classroom_id) REFERENCES classrooms(classroom_id),
 CONSTRAINT fk_change_slot FOREIGN KEY (requested_time_slot_id) REFERENCES time_slots(time_slot_id),
 CONSTRAINT chk_change_day CHECK (requested_day_of_week IS NULL OR requested_day_of_week BETWEEN 1 AND 7)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS os_job_metrics (
 metric_id BIGINT AUTO_INCREMENT PRIMARY KEY,
 request_id BIGINT NULL,
 algorithm VARCHAR(20) NOT NULL,
 priority_value INT NOT NULL DEFAULT 3,
 arrival_sequence BIGINT NOT NULL,
 queued_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 started_at DATETIME NULL,
 finished_at DATETIME NULL,
 waiting_ms BIGINT NULL,
 turnaround_ms BIGINT NULL,
 outcome VARCHAR(30) NULL,
 INDEX idx_os_metrics_queue (queued_at, priority_value),
 CONSTRAINT fk_metric_request FOREIGN KEY (request_id) REFERENCES booking_requests(request_id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS deadlock_demo_runs (
 demo_id BIGINT AUTO_INCREMENT PRIMARY KEY,
 scenario_name VARCHAR(100) NOT NULL,
 detected BOOLEAN NOT NULL,
 resolution VARCHAR(255) NOT NULL,
 details JSON NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

DROP VIEW IF EXISTS v_faculty_booking_history;
CREATE VIEW v_faculty_booking_history AS
 SELECT b.booking_id,b.requester_user_id,u.full_name AS faculty_name,c.room_code,b.booking_date,b.start_time,b.end_time,b.purpose,b.status,b.created_at
 FROM bookings b JOIN users u ON u.user_id=b.requester_user_id JOIN classrooms c ON c.classroom_id=b.classroom_id;
DROP VIEW IF EXISTS v_room_utilization;
CREATE VIEW v_room_utilization AS
 SELECT c.classroom_id,c.room_code,c.capacity,COUNT(b.booking_id) AS confirmed_bookings,
 COALESCE(SUM(TIME_TO_SEC(TIMEDIFF(b.end_time,b.start_time))),0) AS booked_seconds
 FROM classrooms c LEFT JOIN bookings b ON b.classroom_id=c.classroom_id AND b.status='CONFIRMED'
 GROUP BY c.classroom_id,c.room_code,c.capacity;
DROP VIEW IF EXISTS v_pending_requests;
CREATE VIEW v_pending_requests AS
 SELECT r.request_id,r.requester_user_id,u.full_name AS requester,c.room_code,r.request_type,r.requested_date,r.start_time,r.end_time,r.purpose,r.status,r.created_at
 FROM booking_requests r JOIN users u ON u.user_id=r.requester_user_id JOIN classrooms c ON c.classroom_id=r.classroom_id WHERE r.status='PENDING';
DELIMITER $$
DROP TRIGGER IF EXISTS trg_booking_confirmed_history$$
CREATE TRIGGER trg_booking_confirmed_history AFTER INSERT ON bookings FOR EACH ROW
BEGIN
 INSERT INTO booking_history(booking_id,request_id,actor_user_id,action,details)
 VALUES(NEW.booking_id,NEW.request_id,NEW.requester_user_id,'BOOKING_INSERTED',JSON_OBJECT('room_id',NEW.classroom_id,'date',NEW.booking_date,'start',NEW.start_time,'end',NEW.end_time));
END$$
DROP TRIGGER IF EXISTS trg_booking_status_history$$
CREATE TRIGGER trg_booking_status_history AFTER UPDATE ON bookings FOR EACH ROW
BEGIN
 IF OLD.status <> NEW.status THEN
  INSERT INTO booking_history(booking_id,request_id,actor_user_id,action,details)
  VALUES(NEW.booking_id,NEW.request_id,NEW.requester_user_id,'BOOKING_STATUS_CHANGED',JSON_OBJECT('from',OLD.status,'to',NEW.status));
 END IF;
END$$
DROP PROCEDURE IF EXISTS sp_check_room_availability$$
CREATE PROCEDURE sp_check_room_availability(IN p_room INT, IN p_date DATE, IN p_start TIME, IN p_end TIME)
BEGIN
 SELECT NOT EXISTS(SELECT 1 FROM bookings b WHERE b.classroom_id=p_room AND b.booking_date=p_date AND b.status='CONFIRMED' AND b.start_time<p_end AND b.end_time>p_start)
 AND NOT EXISTS(
  SELECT 1 FROM timetable_entries e JOIN timetables t ON t.timetable_id=e.timetable_id JOIN time_slots s ON s.time_slot_id=e.time_slot_id
  WHERE e.classroom_id=p_room AND e.day_of_week=DAYOFWEEK(p_date) AND t.status='PUBLISHED' AND s.start_time<p_end AND s.end_time>p_start
 ) AS available;
END$$
DROP PROCEDURE IF EXISTS sp_get_room_utilization$$
CREATE PROCEDURE sp_get_room_utilization() BEGIN SELECT * FROM v_room_utilization ORDER BY confirmed_bookings DESC; END$$
DROP PROCEDURE IF EXISTS sp_get_faculty_booking_history$$
CREATE PROCEDURE sp_get_faculty_booking_history(IN p_user_id INT)
BEGIN SELECT * FROM v_faculty_booking_history WHERE requester_user_id=p_user_id ORDER BY booking_date DESC,start_time DESC; END$$
DELIMITER ;
