-- Attendance Recording System Schema
-- Date: 2026-01-20
-- Description: Track student attendance with check-in/check-out times

CREATE TABLE IF NOT EXISTS attendance (
    attendance_id INT(11) AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(50) NOT NULL,
    track_id INT(11) NOT NULL,
    identity_name VARCHAR(255) DEFAULT NULL,
    check_in_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    check_out_time TIMESTAMP NULL DEFAULT NULL,
    duration_seconds INT(11) DEFAULT 0,
    status ENUM('present', 'left', 'unknown') DEFAULT 'present',
    notes TEXT DEFAULT NULL,
    
    -- Indexes
    INDEX idx_session (session_id),
    INDEX idx_identity (identity_name),
    INDEX idx_track (track_id),
    INDEX idx_status (status),
    INDEX idx_check_in (check_in_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Verify table creation
DESCRIBE attendance;
