-- Migration: Add identity_name column to students table
-- Date: 2026-01-20
-- Description: Store recognized face identities in students table for cross-session tracking

-- Add identity_name to students table
ALTER TABLE students 
ADD COLUMN identity_name VARCHAR(255) DEFAULT NULL AFTER track_id;

-- Add index for faster identity lookups
CREATE INDEX idx_student_identity ON students(identity_name);

-- Add composite index for session + identity queries
CREATE INDEX idx_session_identity ON students(session_id, identity_name);

-- Verify changes
DESCRIBE students;
