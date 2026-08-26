-- materialized view for monthly clinic discharges
CREATE MATERIALIZED VIEW clinic_monthly_discharges AS
SELECT 
    clinic_id,
    DATE_TRUNC('month', created_at) AS discharge_month,
    COUNT(id) AS total_discharges
FROM appointments
WHERE status = 'DISCHARGED'
GROUP BY clinic_id, DATE_TRUNC('month', created_at);

-- unique index for the materialized view
CREATE UNIQUE INDEX idx_clinic_month_discharge 
ON clinic_monthly_discharges (clinic_id, discharge_month);

-- stored function to refresh the view safely
CREATE OR REPLACE FUNCTION refresh_clinic_discharges_mv()
RETURNS void AS $$
BEGIN
    -- refreshes data without locking the view for read queries
    REFRESH MATERIALIZED VIEW CONCURRENTLY clinic_monthly_discharges;
END;
$$ LANGUAGE plpgsql;