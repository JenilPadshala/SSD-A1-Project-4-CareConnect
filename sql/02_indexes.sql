-- prevent a patient from having more than one active consultation
CREATE UNIQUE INDEX idx_active_consult ON appointments (patient_id) 
WHERE status IN ('WAITING', 'IN_CONSULTATION');

-- target discharged appointments to eliminate sequential scans and optimize window analytics
CREATE INDEX idx_appointments_analytics
ON appointments (clinic_id, ((created_at AT TIME ZONE 'UTC')::date))
WHERE status = 'DISCHARGED';