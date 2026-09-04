# SSD-A1-Project-4-CareConnect

## [Github Repository Link: https://github.com/JenilPadshala/SSD-A1-Project-4-CareConnect](https://github.com/JenilPadshala/SSD-A1-Project-4-CareConnect)
## Final Commit Hash: 626b4eb575917db822e26671bdcdfa02002f7990

## Step 1: Database Provisioning & Schema Constraints

### Creating PostgreSQL Tables

#### Overview

Four tables: patients and their HSA wallets, clinics, a ledger of wallet movements, and appointments.

#### File

- `sql/01_schema_ddl.sql`

```bash
psql -d careconnect -f sql/01_schema_ddl.sql
```

![Relational ERD](docs/relational_erd.png)

#### What it creates

- `patients` — name and an HSA balance that cannot go below `0.00`.
- `clinics` — name, latitude, longitude, and whether the clinic is still taking patients.
- `wallet_audit_logs` — one row per HSA movement (`amount_changed`, `action_type`, `balance_after`, `timestamp`). Step 1 only creates the table. The trigger in Step 2 is what writes into it.
- `appointments` — patient, clinic, copay, and status (`WAITING`, `IN_CONSULTATION`, or `DISCHARGED`).



### MongoDB collections



#### Overview

Unstructured data that does not belong in the relational tables: specialist catalogs, patient reviews, and live nurse locations.

#### File

- `mongo/01_collections_and_indexes.js`

```bash
mongosh mongo/01_collections_and_indexes.js
```

The same script also builds the `2dsphere` and TTL indexes on `NursePings`. Those belong to Step 2; they are documented there.

#### What it creates

On `careconnect_db`:

- `MedicalCatalogs` — specialist availability and medication details
- `PatientReviews` — ratings, bedside-manner tags, and timestamps
- `NursePings` — GeoJSON location logs for dispatched mobile nurses

Document field names live in `docs/mongo_schema_map.json`. Mongo does not enforce that file as a validator.

### Assumptions made by the team:

- Primary keys are UUIDs, not integers.
- `action_type` is only `CREDIT` or `DEBIT`.
- Deleting a patient or clinic also deletes their appointments.
- Mongo document fields:
  - `MedicalCatalogs` — `clinic_id`, `specialist_name`, `specialty`,
  `availability` (`day`, `slots`), `medications_handled` (`name`,
  `dosage_forms`, `requires_rx`)
  - `PatientReviews` — `appointment_id`, `clinic_id`, `patient_id`,
  `rating`, `bedside_manner_tags`, `review_text`, `created_at`
  - `NursePings` — `nurse_id`, `active`, GeoJSON `location`, `created_at`

---



## Step 2: Database-Heavy Engineering Tasks



### Partial indexing



#### Overview

A patient can have many `DISCHARGED` appointments, but only one open visit at a time (`WAITING` or `IN_CONSULTATION`).

#### File

- `sql/02_indexes.sql`

```bash
psql -d careconnect -f sql/02_indexes.sql
```



#### What it creates

- `idx_active_consult` — unique on `appointments.patient_id` for rows that are still open. A second open visit for the same patient is rejected.
- `idx_appointments_analytics` — on clinic and calendar day, for `DISCHARGED` rows only. Not required by the assignment; it is there for Workflow 2.



### PostgreSQL trigger (audit logging)



#### Overview

When a patient's `hsa_balance` changes, a trigger writes the movement into `wallet_audit_logs`. Ordinary updates should not insert into the ledger by hand.

#### File

- `sql/03_triggers_and_audit.sql`

```bash
psql -d careconnect -f sql/03_triggers_and_audit.sql
```



#### What it creates

`trigger_audit_hsa_balance` runs `AFTER UPDATE OF hsa_balance` on `patients`. The function `log_hsa_balance_change()` writes:

- `amount_changed` — size of the move (always positive)
- `action_type` — `CREDIT` if the balance rose, `DEBIT` if it fell
- `balance_after` — the new balance

Workflow 1 only updates `patients.hsa_balance`. The trigger is what creates the matching audit row.

### Materialized view



#### Overview

Monthly discharge counts per clinic, stored so they do not have to be recomputed from `appointments` every time.

#### File

- `sql/05_materialized_views.sql`

```bash
psql -d careconnect -f sql/05_materialized_views.sql
```



#### What it creates

- `clinic_monthly_discharges` — `DISCHARGED` appointments grouped by `clinic_id` and calendar month, with `total_discharges`
- `idx_clinic_month_discharge` — unique on `(clinic_id, discharge_month)`, needed for a concurrent refresh
- `refresh_clinic_discharges_mv()` — refreshes the view without blocking readers

```sql
SELECT refresh_clinic_discharges_mv();
```

The PostgreSQL seeder in Step 4 calls this after the load.

### MongoDB geospatial and TTL indexes



#### Overview

A `2dsphere` index on nurse locations for Workflow 3, and a TTL index that drops pings after two hours.

#### File

- `mongo/01_collections_and_indexes.js` (same file as Step 1)

```bash
mongosh mongo/01_collections_and_indexes.js
```



#### What it creates

On `NursePings` in `careconnect_db`:

- a `2dsphere` index on `location`
- a TTL index on `created_at` with `expireAfterSeconds: 7200`



### Assumptions made by the team:

- `idx_appointments_analytics` is extra; the assignment only asks for the active-consult unique index.
- Calendar days for that index are taken in UTC.
- The materialized view counts only `DISCHARGED` appointments, by calendar month of `created_at`.

---



## Step 3: Complex Database Workflows (Pure Scripts)



### Workflow 1: Atomic Appointment (Stored Procedure)



#### Overview

A PL/pgSQL Stored Procedure to safely deduct HSA balances, create the appointment, and log the audit trail atomically. It rolls back on constraint failure.

#### File

- `sql/04_stored_procedures.sql`

```bash
psql -d careconnect -f sql/04_stored_procedures.sql
```



#### What it creates

- `create_appointment_atomic()` — A stored procedure that starts a transaction, locks the patient and clinic rows to prevent race conditions, deducts the copay from the HSA balance, and creates a `WAITING` appointment. If the HSA balance is insufficient, it raises an exception and rolls back. The `wallet_audit_logs` record is inserted automatically by the trigger.



### Workflow 2: SQL Window Analytics



#### Overview

A SQL script utilizing CTEs and Window Functions to calculate a 7-day moving average of copay revenue per clinic, ranked via `DENSE_RANK()`.

#### File

- `sql/06_window_analytics.sql`

```bash
psql -d careconnect -f sql/06_window_analytics.sql
```



#### What it executes

Executes a query calculating the 7-day moving average of copay revenue (using `DISCHARGED` appointments) and returns the calendar day, clinic name, daily revenue, 7-day rolling total, 7-day moving average, days in window, and clinic rank based on the moving average.

### Workflow 3: Nearest Mobile Nurse



#### Overview

A MongoDB `$geoNear` aggregation pipeline locating the closest active mobile nurse to a patient's coordinates within a 5km radius.

#### File

- `mongo/02_workflow3_geonear.js`

```bash
mongosh mongo/02_workflow3_geonear.js
```



#### What it executes

Executes a MongoDB aggregation pipeline on `NursePings` utilizing the `$geoNear` stage to find the closest documents to a patient's geospatial point, filters for active nurses, and returns the nearest active mobile nurse.

### Workflow 4: Multi-Faceted Review Analytics



#### Overview

A MongoDB aggregation pipeline using `$facet` to extract rating buckets, frequent sentiment tags via `$unwind`, and global average ratings.

#### File

- `mongo/03_workflow4_facet.js`

```bash
mongosh mongo/03_workflow4_facet.js
```



#### What it executes

Executes a MongoDB pipeline on `PatientReviews` that leverages `$facet` to simultaneously output the distribution of reviews across 1-5 stars, the most frequently used bedside manner tags (via `$unwind`), and the platform's overall average rating.

### Assumptions made by the team:

- **Workflow 1**: New appointments are initialized with a `'WAITING'` status. The procedure relies entirely on the trigger from Step 2 to generate the audit log.
- **Workflow 2**: Only `'DISCHARGED'` appointments generate revenue. Missing calendar days are explicitly padded with `0.00` to guarantee the 7-day average covers 7 chronological calendar days.
- **Workflow 3**: The maximum search radius for a mobile nurse is capped at 5,000 meters (5km). The result is limited to a single closest nurse (`$limit: 1`) who must be active (`active: true`).
- **Workflow 4**: The rating distribution buckets assume standard 1 to 5 star ratings. The most frequent bedside manner tags result is limited to the top 5 tags.

---



## Step 4: Data Generation & Stress Testing



### Seeding MongoDB Collections

This process populates the unstructured NoSQL collections with high-volume mock data to prove the indexing and aggregation pipelines work at scale. It utilizes Python and the Faker library.

**Prerequisites**
Install the necessary Python dependencies for database connections and data mocking:

```bash
pip install -r data_generation/requirements.txt
```

To seed the MongoDB collections, run the following command:

```bash
python data_generation/mongo_seeder.py
```



#### Seeded Collections Overview

- MedicalCatalogs: 1,000 documents populated with randomized physician names, specialties, available time slots, and nested medication catalogs.
- PatientReviews: 100,000 documents processed and inserted in memory-safe batches of 10,000, including randomized 1-5 star ratings, bedside-manner tags, and realistic timestamps.
- NursePings: 500,000 geospatial telemetry documents distributed evenly across 5 unique nurses, localized within a ~5km radius of the base coordinates.



### Seeding PostgreSQL Tables

This process populates the structured PostgreSQL tables with high-volume mock data to prove the indexes, audit trigger, and analytics queries work at scale. It utilizes Python and the Faker library.

**Prerequisites**
Install the necessary Python dependencies for database connections and data mocking:

```bash
pip install -r data_generation/requirements.txt
```

The tables, partial index, audit trigger, and materialized view from Steps 1 and 2 must already exist.

```bash
createdb careconnect
psql -d careconnect -f sql/01_schema_ddl.sql
psql -d careconnect -f sql/02_indexes.sql
psql -d careconnect -f sql/03_triggers_and_audit.sql
psql -d careconnect -f sql/05_materialized_views.sql
```



#### Running it

```bash
python data_generation/postgres_seeder.py
```

```bash
CARECONNECT_DSN="dbname=careconnect host=localhost user=postgres" python data_generation/postgres_seeder.py
```



#### Seeded Tables Overview

- clinics: 250 rows with Faker-generated names, coordinates jittered around eight Indian metro areas, and about 8% marked as not accepting patients.
- patients: 25,000 rows with Faker-generated names; `hsa_balance` is the end of that patient's chained ledger and never goes below zero.
- appointments: 60,000 rows loaded with `COPY` in batches of 20,000, including 6,000 open (`WAITING` / `IN_CONSULTATION`) visits on distinct patients in the last two days and the rest `DISCHARGED` over about 540 days.
- wallet_audit_logs: at least 100,000 chained CREDIT/DEBIT rows inserted with `COPY`, plus 4,000 extra rows written by live `UPDATE`s so the Step 2 audit trigger also fires.



### Assumptions made by the team:

- The Postgres seeder is deterministic (`random.seed(20250401)` and `Faker.seed(20250401)`). Re-running it on a fresh database should give the same table counts. IDs still come from `uuid.uuid4()`, and the 540-day window is anchored on `datetime.now()`, so pasted `EXPLAIN ANALYZE` times will not match bit-for-bit.
- The Mongo seeder does not seed `random` or Faker. Collection counts stay the same (1,000 / 100,000 / 500,000) but documents, nurse IDs, and `executionStats` numbers change every run.
- Both seeders wipe first: Postgres `TRUNCATE`s the four tables; Mongo `delete_many`s `MedicalCatalogs`, `PatientReviews`, and `NursePings`.
- Postgres clinics sit around eight Indian metros (Hyderabad, Mumbai, Delhi, Bengaluru, Chennai, Kolkata, Pune, Ahmedabad). `NursePings` are jittered around the IIITH coordinates hard-coded in Workflow 3, so `$geoNear` with `maxDistance: 5000` actually finds them. Hyderabad clinics can land near that point; clinics in the other cities will not.
- `NursePings` uses only 5 nurse IDs (not 500,000 nurses). Workflow 3 still runs over the 500,000 ping documents; `active` is random per ping, so a nurse can be inactive on a given run.

---



## Performance Proof

Taken after Step 4 seeding (and after Postgres `ANALYZE`). Full plans are in `performance/`. The numbers below are from those files; they will move a little on the next run.

### Workflow 2: SQL Window Analytics



#### Overview

`EXPLAIN (ANALYZE, BUFFERS)` of `sql/06_window_analytics.sql`, to show discharged copays are read through `idx_appointments_analytics` rather than a sequential scan.

#### File

- `performance/postgres_explain_analyzes.txt`

```bash
{ echo "EXPLAIN (ANALYZE, BUFFERS)"; cat sql/06_window_analytics.sql; } | psql -d careconnect -o performance/postgres_explain_analyzes.txt
```



#### What it proves

- `daily_totals` reads `appointments` with `Index Scan using idx_appointments_analytics` (54,000 discharged rows). There is no `Seq Scan`.
- `clinics` is read with `Index Scan using clinics_pkey` (250 rows).
- The window functions run over the clinic calendar, not the appointments table: 250 clinics × 539 days = **134,750** rows. The planner's 269,495 was an estimate; 134,750 is what actually ran. Most of the **405.242 ms** is that fan-out and the `DENSE_RANK` sort, not the index scan (~29 ms).
- Table pages came from cache (`shared hit=54414`, no `shared read`). The rank sort still spilled: `Sort Method: external merge` with `temp read=1020 written=1023`.



### Workflow 3: Nearest Mobile Nurse



#### Overview

`explain("executionStats")` of the `$geoNear` pipeline on `NursePings`, to show the `2dsphere` index is used.

#### File

- `performance/mongo_execution_stats.json` (`workflow3`)

```bash
mongosh mongo/02_workflow3_geonear.js
```

The committed JSON is `NursePings.explain("executionStats").aggregate(...)` for that same pipeline, stored under the `workflow3` key.

#### What it proves

- Winning plan is `GEO_NEAR_2DSPHERE` on `location_2dsphere`, then `FETCH` with `active: true`. No `COLLSCAN`.
- **177** keys and **193** docs examined, against 500,000 pings. **6 ms**.
- The geo cursor reported `nReturned: 32` (active pings inside 5 km). `$limit: 1` then keeps a single nurse (`nReturned: 1` on that stage). 32 is not the script's printed result.



### Workflow 4: Multi-Faceted Review Analytics



#### Overview

`explain("executionStats")` of the `$facet` pipeline on `PatientReviews`.

#### File

- `performance/mongo_execution_stats.json` (`workflow4`)

```bash
mongosh mongo/03_workflow4_facet.js
```



#### What it proves

- The cursor plan is `COLLSCAN` then `PROJECTION_SIMPLE` (`rating`, `bedside_manner_tags`). **100,000** docs examined, **0** keys, **181 ms**.
- That scan is expected: there is no `$match` before `$facet`, and every facet needs every review. `01_collections_and_indexes.js` does not put an index on `PatientReviews`.
- `$facet` then splits that one projection: rating buckets (~113 ms estimate), tag unwind/group/limit 5 (~47 ms), global average (~12 ms), about **172 ms** for the facet stage. It is not three separate collection reads.
- There is no `facetTimings` field in the JSON; those millisecond figures are the stage `executionTimeMillisEstimate` values.



### Assumptions made by the team:

- `EXPLAIN` / `executionStats` times are from one capture after seeding. Re-running will not reproduce them exactly (see Step 4).
- Workflow 4's `COLLSCAN` is treated as correct, not a missing index.
- The two Mongo explains were merged by hand into one file (`workflow3` / `workflow4`). Redirecting a single `mongosh --eval` over `mongo_execution_stats.json` would replace the other key.
