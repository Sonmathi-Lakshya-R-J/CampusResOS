USE campusresos;

CREATE TABLE IF NOT EXISTS os_job_metrics (
    metric_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    request_id INT NULL,
    algorithm ENUM('FCFS','SJF','PRIORITY') NOT NULL,
    priority_value INT NOT NULL DEFAULT 3,
    arrival_sequence BIGINT NOT NULL,
    queued_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    waiting_ms BIGINT NULL,
    turnaround_ms BIGINT NULL,
    outcome VARCHAR(30) NULL,

    INDEX idx_os_metrics_queue (queued_at, priority_value),
    INDEX idx_os_metrics_request (request_id)
) ENGINE=InnoDB;
