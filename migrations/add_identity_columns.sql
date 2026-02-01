-- Migration: Add identity_name columns to behavioral_metrics and alerts tables
-- Date: 2026-01-20
-- Description: Store recognized face identities alongside track IDs

-- Add identity_name to behavioral_metrics table
ALTER TABLE behavioral_metrics 
ADD COLUMN identity_name VARCHAR(255) DEFAULT NULL AFTER track_id;

-- Add index for faster identity lookups
CREATE INDEX idx_identity_name ON behavioral_metrics(identity_name);

-- Add identity_name to alerts table
ALTER TABLE alerts
ADD COLUMN identity_name VARCHAR(255) DEFAULT NULL AFTER track_id;

-- Add index for faster identity lookups in alerts
CREATE INDEX idx_alerts_identity ON alerts(identity_name);

-- Verify changes
DESCRIBE behavioral_metrics;
DESCRIBE alerts;
