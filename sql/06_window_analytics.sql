-- workflow 2: 7 day moving average of copay revenue per clinic
--
-- only discharged appointments count as revenue, since the copay is earned
-- once the visit is finished. this is the same rule 05_materialized_views.sql
-- already uses for clinic_monthly_discharges.
--
-- created_at is timestamptz, so the day a copay falls into follows the session
-- time zone. run the seed script and this query in the same session so the
-- buckets line up.

WITH daily_totals AS (
    -- one row per clinic per day that actually had a discharge
    SELECT
        clinic_id,
        created_at::date AS revenue_date,
        SUM(copay_amount) AS daily_revenue
    FROM appointments
    WHERE status = 'DISCHARGED'
    GROUP BY clinic_id, created_at::date
),
reporting_period AS (
    -- the calendar range the data covers
    SELECT
        MIN(revenue_date) AS start_date,
        MAX(revenue_date) AS end_date
    FROM daily_totals
),
clinic_calendar AS (
    -- give every clinic a row for every day in the range so that a day with
    -- no discharges counts as 0.00 instead of dropping out of the window
    SELECT
        c.id   AS clinic_id,
        c.name AS clinic_name,
        d::date AS revenue_date
    FROM clinics c
    CROSS JOIN reporting_period p
    CROSS JOIN generate_series(
        p.start_date::timestamp,
        p.end_date::timestamp,
        INTERVAL '1 day'
    ) AS d
),
daily_revenue AS (
    SELECT
        cal.clinic_id,
        cal.clinic_name,
        cal.revenue_date,
        COALESCE(t.daily_revenue, 0.00) AS daily_revenue
    FROM clinic_calendar cal
    LEFT JOIN daily_totals t
           ON t.clinic_id    = cal.clinic_id
          AND t.revenue_date = cal.revenue_date
),
rolling AS (
    -- the calendar above guarantees one row per clinic per day, so 6 preceding
    -- rows plus the current row is exactly a 7 day span
    SELECT
        clinic_id,
        clinic_name,
        revenue_date,
        daily_revenue,
        SUM(daily_revenue) OVER seven_days          AS rolling_total_7day,
        ROUND(AVG(daily_revenue) OVER seven_days, 2) AS moving_avg_7day,
        COUNT(*) OVER seven_days                     AS days_in_window
    FROM daily_revenue
    WINDOW seven_days AS (
        PARTITION BY clinic_id
        ORDER BY revenue_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    )
)
SELECT
    revenue_date,
    clinic_name,
    daily_revenue,
    rolling_total_7day,
    moving_avg_7day,
    days_in_window,
    -- clinics tied on the same average share a rank and the next clinic down
    -- still gets the next number, which is why this is DENSE_RANK and not RANK
    DENSE_RANK() OVER (
        PARTITION BY revenue_date
        ORDER BY moving_avg_7day DESC
    ) AS clinic_rank
FROM rolling
ORDER BY revenue_date, clinic_rank, clinic_name;
