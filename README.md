# SSD-A1-Project-4-CareConnect

## Workflow 2 – SQL Window Analytics

### Overview

Workflow 2 reports a 7 day moving average of copay revenue for every clinic and
ranks the clinics against each other on each day using `DENSE_RANK()`.

The query is built out of CTEs and runs against the PostgreSQL tables created in
`01_schema_ddl.sql`.

### What counts as revenue

Only appointments with status `DISCHARGED` are counted, since the copay is
earned once the visit is finished. This is the same rule
`clinic_monthly_discharges` already uses in `05_materialized_views.sql`.

### How the 7 day window is built

A clinic does not see patients every single day, and an average that quietly
skipped the empty days would make a clinic that opened twice in a week look just
as strong as one that opened every day. So the query first builds a calendar
with one row per clinic per day across the whole reporting range, fills the
missing days with `0.00`, and only then averages over
`ROWS BETWEEN 6 PRECEDING AND CURRENT ROW`. Because the calendar has no holes,
those 7 rows are always 7 calendar days.

`DENSE_RANK()` is used instead of `RANK()` so that when two clinics land on the
same average they share a position and the next clinic down still gets the next
number rather than having one skipped.

### Output columns


| Column               | Meaning                                                                          |
| -------------------- | -------------------------------------------------------------------------------- |
| `revenue_date`       | the day being reported                                                           |
| `clinic_name`        | the clinic                                                                       |
| `daily_revenue`      | copay taken that day, `0.00` if the clinic was quiet                             |
| `rolling_total_7day` | copay taken over that day and the 6 days before it                               |
| `moving_avg_7day`    | `rolling_total_7day` divided by `days_in_window`, to 2 decimals                  |
| `days_in_window`     | how many days the average covers, below 7 only for the first 6 days of the range |
| `clinic_rank`        | position among all clinics that day by `moving_avg_7day`, ties share a rank      |




### Files

Two files were added for workflow 2:

- `06_seed_window_analytics.sql` (test data only, needs to be removed before final submission)
- `06_window_analytics.sql`



### Executing Workflow 2

```bash
psql -d careconnect -f sql/04_seed_window_analytics.sql
psql -d careconnect -f sql/04_window_analytics.sql
```

The seed script empties the four tables before it inserts, so do not point it at
data you want to keep.

### What the seed data covers

The seeded rows are chosen so the interesting cases are all visible in the
output rather than having to be imagined:

- Northside takes two copays on 3 March, and they are added together into one
daily figure of 200.00.
- Northside has a 400.00 appointment on 5 March that is still `IN_CONSULTATION`,
and it stays out of the report.
- Riverside and Lakeview both take 700.00 on 5 March and nothing else that week,
so they sit tied on the same rank every day from 5 March to 15 March.
- On 12 March that 700.00 drops off the back of the window and both fall to
0.00, which shows the window really is sliding.
- Hilltop has never discharged anyone, so it stays at 0.00 and ranks last.
- The first six days show `days_in_window` climbing from 1 to 7.



### A note on dates

`created_at` is a `TIMESTAMPTZ`, so which calendar day a copay falls into
depends on the session time zone. The seed timestamps are written without an
offset, so PostgreSQL reads them in whatever time zone the session happens to be
using and the query then buckets them back the same way. Running both files in
the same session gives the same answer no matter where it is run.

---



## Workflow 3 – Nearest Mobile Nurse



### Overview

Workflow 3 uses MongoDB's `$geoNear` aggregation stage to locate the
nearest active mobile nurse to a patient's current coordinates.

The workflow operates on the `NursePings` collection in the
`careconnect_db` database.

### MongoDB Setup

The `NursePings` collection uses a `2dsphere` index on the `location`
field for geospatial queries.
That is already done in Step 2.

### NursePing Document Structure

Test NursePing documents use the following structure:

```javascript
{
    nurse_id: "N001",
    active: true,
    location: {
        type: "Point",
        coordinates: [longitude, latitude]
    },
    created_at: new Date()
}
```

Also we have two files for this workflow 3

- `02_seed_nurse_pings.js`
- `02_workflow3_geonear.js`

To add a sample test data for nurse pings you can run the following command (This is seeding script ONLY TO BE USED FOR LOCAL TESTING, AND NOT TO INCLUDE IN FINAL PROJECT):

```bash
mongosh mongo/02_seed_nurse_pings.js
```

And then for retrieving the nearest active nurses you can run the following command (This is the script that uses `$geoNear` to retrieve the nearest active nurses that have pinged recently):

```bash
mongosh mongo/02_workflow3_geonear.js
```

Also I have HARD-CODED current patient location, that you will be able to see in `02_workflow3_geonear.js`  

You can add your test datas in this collection and run this retrieving script for more testing.

---



## Workflow 4 – Multi-Faceted Review Analytics



### Overview

Workflow 4 uses MongoDB's `$facet` aggregation stage to simultaneously extract rating buckets, determine frequent sentiment tags using the `$unwind` operator, and calculate the global average rating across the platform.

The workflow operates on the `PatientReviews` collection in the `careconnect_db` database.

### MongoDB Setup

The `PatientReviews` collection utilizes standard indexes on fields like `clinic_id` and `rating` to optimize the aggregation pipeline operations. 

### PatientReview Document Structure

Test PatientReview documents use the following structure:

```javascript

{

    appointment_id: "A001",

    clinic_id: "C001",

    patient_id: "P001",

    rating: 5,

    bedside_manner_tags: ["empathetic", "punctual", "clear-instructions"],

    review_text: "Great experience.",

    created_at: new Date()

}
```



### Executing Workflow 4:

I have added two files for workflow 4:

- `03_seed_workflow4.js` (temporary, need to be removed before final submission)
- `03_workflow4_facet.js`

Run the following commands to test workflow 4:

```bash
mongosh mongo/03_seed_workflow4.js
mongosh mongo/03_workflow4_facet.js
```

---

