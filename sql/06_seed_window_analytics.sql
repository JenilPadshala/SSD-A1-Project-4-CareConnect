-- seed data for testing workflow 2 locally, not meant for the final submission
--
-- the rows below are picked to cover the cases the moving average has to get
-- right: two visits on one day, days with nothing at all, appointments that are
-- not discharged yet, a clinic that has earned nothing, a tie between clinics,
-- and revenue old enough to fall out of the back of the 7 day window.
--
-- the timestamps have no utc offset on purpose. postgres reads them in the
-- session time zone and 04_window_analytics.sql buckets them back the same way,
-- so the results are the same no matter where this is run.

DELETE FROM wallet_audit_logs;
DELETE FROM appointments;
DELETE FROM patients;
DELETE FROM clinics;

INSERT INTO clinics (id, name, latitude, longitude, is_accepting_patients) VALUES
('11111111-1111-1111-1111-111111111111', 'Northside Family Clinic',  40.7831, -73.9712, TRUE),
('22222222-2222-2222-2222-222222222222', 'Riverside Urgent Care',    40.7580, -73.9855, TRUE),
('33333333-3333-3333-3333-333333333333', 'Lakeview Health Center',   40.7061, -73.9969, TRUE),
('44444444-4444-4444-4444-444444444444', 'Hilltop Community Clinic', 40.8296, -73.9262, FALSE);

INSERT INTO patients (id, name, hsa_balance) VALUES
('aaaaaaaa-0000-0000-0000-000000000001', 'Ana Ruiz',      1500.00),
('aaaaaaaa-0000-0000-0000-000000000002', 'Ben Carter',     900.00),
('aaaaaaaa-0000-0000-0000-000000000003', 'Chi Nakamura',  2200.00),
('aaaaaaaa-0000-0000-0000-000000000004', 'Dara Osei',      450.00),
('aaaaaaaa-0000-0000-0000-000000000005', 'Elena Petrova', 1750.00);

INSERT INTO appointments (patient_id, clinic_id, copay_amount, status, created_at) VALUES
-- northside trades most days, mar 5, 8, 9, 15 and 16 are quiet
('aaaaaaaa-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 120.00, 'DISCHARGED', '2025-03-03 12:00:00'),
('aaaaaaaa-0000-0000-0000-000000000002', '11111111-1111-1111-1111-111111111111',  80.00, 'DISCHARGED', '2025-03-03 15:30:00'),
('aaaaaaaa-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 150.00, 'DISCHARGED', '2025-03-04 12:00:00'),
('aaaaaaaa-0000-0000-0000-000000000003', '11111111-1111-1111-1111-111111111111', 200.00, 'DISCHARGED', '2025-03-06 12:00:00'),
('aaaaaaaa-0000-0000-0000-000000000002', '11111111-1111-1111-1111-111111111111', 100.00, 'DISCHARGED', '2025-03-07 12:00:00'),
('aaaaaaaa-0000-0000-0000-000000000004', '11111111-1111-1111-1111-111111111111', 250.00, 'DISCHARGED', '2025-03-10 12:00:00'),
('aaaaaaaa-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 175.00, 'DISCHARGED', '2025-03-11 12:00:00'),
('aaaaaaaa-0000-0000-0000-000000000005', '11111111-1111-1111-1111-111111111111', 125.00, 'DISCHARGED', '2025-03-12 12:00:00'),
('aaaaaaaa-0000-0000-0000-000000000003', '11111111-1111-1111-1111-111111111111', 300.00, 'DISCHARGED', '2025-03-13 12:00:00'),
('aaaaaaaa-0000-0000-0000-000000000002', '11111111-1111-1111-1111-111111111111',  90.00, 'DISCHARGED', '2025-03-14 12:00:00'),

-- still in the chair on mar 5, so none of this 400.00 should reach the report
('aaaaaaaa-0000-0000-0000-000000000004', '11111111-1111-1111-1111-111111111111', 400.00, 'IN_CONSULTATION', '2025-03-05 12:00:00'),

-- riverside and lakeview both take exactly 700.00 on mar 5 and nothing else
-- that week, so they should be tied every day from mar 5 to mar 15
('aaaaaaaa-0000-0000-0000-000000000005', '22222222-2222-2222-2222-222222222222', 700.00, 'DISCHARGED', '2025-03-05 12:00:00'),
('aaaaaaaa-0000-0000-0000-000000000003', '33333333-3333-3333-3333-333333333333', 700.00, 'DISCHARGED', '2025-03-05 12:00:00'),

-- one late visit breaks the tie on the last day and stretches the reporting
-- range out to mar 16
('aaaaaaaa-0000-0000-0000-000000000001', '33333333-3333-3333-3333-333333333333',  50.00, 'DISCHARGED', '2025-03-16 12:00:00'),

-- hilltop has never discharged anyone, so it should sit at 0.00 throughout
('aaaaaaaa-0000-0000-0000-000000000005', '44444444-4444-4444-4444-444444444444', 150.00, 'WAITING', '2025-03-06 12:00:00');
