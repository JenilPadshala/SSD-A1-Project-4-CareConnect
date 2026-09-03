# SSD-A1-Project-4-CareConnect
[Github Repository Link](https://github.com/JenilPadshala/SSD-A1-Project-4-CareConnect)
---
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
python data_generation/mongo_seeder_1.py
```



#### Seeded Collections Overview

- MedicalCatalogs: 1,000 documents populated with randomized physician names, specialties, available time slots, and nested medication catalogs.
- PatientReviews: 100,000 documents processed and inserted in memory-safe batches of 10,000, including randomized 1-5 star ratings, bedside-manner tags, and realistic timestamps.
- NursePings: 500,000 geospatial telemetry documents distributed evenly across 5 unique nurses, localized within a ~5km radius of the base coordinates.



### Seeding PostgreSQL Tables

`data_generation/postgres_seeder.py` fills the four relational tables with
enough rows to clear the assignment's volume requirement:


| Table               | Rows          |
| ------------------- | ------------- |
| `clinics`           | 250           |
| `patients`          | 25,000        |
| `appointments`      | 60,000        |
| `wallet_audit_logs` | 116,000 or so |


The exact ledger count moves a little because the number of movements per
patient is random, but the script will not finish below 100,000.

#### Prerequisites

The script needs `psycopg2-binary` and `Faker`, both of which are in
`data_generation/requirements.txt`:

```bash
pip install -r data_generation/requirements.txt
```

The tables, the partial index, the audit trigger and the materialized view all
have to exist first, so run steps 1 and 2 before seeding:

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

It connects to `dbname=careconnect` on the local socket. To point it anywhere
else, set `CARECONNECT_DSN`:

```bash
CARECONNECT_DSN="dbname=careconnect host=localhost user=postgres" python data_generation/postgres_seeder.py
```

The script truncates all four tables before it loads, so do not run it against
a database holding anything you want to keep. It takes roughly 90 seconds.

#### How the wallet ledger is built

The audit table is the one place in this schema where random numbers would be
actively wrong: `balance_after` is supposed to be the balance the patient was
left with, so it has to follow from the movement before it.

So the script does not generate audit rows independently. It walks each patient
forward through their own sequence of movements, starting from an opening
balance and applying credits and debits in date order, and writes out
`balance_after` at each step. The balance the patient ends on is what goes into
`patients.hsa_balance`. Debits are never allowed to take a patient below zero,
which is the same rule the `CHECK (hsa_balance >= 0.00)` constraint enforces.

Those rows go in with `COPY`, which is fast but bypasses the trigger in
`03_triggers_and_audit.sql` completely. To exercise the real path as well, the
last phase updates `patients.hsa_balance` for 4,000 patients and lets the
trigger write those audit rows itself. Those are the only rows in the table the
script never inserts directly.

#### Data shape

- Appointments are spread over the last 18 months. About 90% are `DISCHARGED`,
which is what `clinic_monthly_discharges` and the workflow 2 moving average
both read.
- The remaining `WAITING` and `IN_CONSULTATION` appointments all go to distinct
patients and are dated within the last two days. The partial unique index from
`02_indexes.sql` allows only one open appointment per patient, so seeding two
for the same patient would fail the load.
- Clinics are scattered around eight metro areas rather than uniformly over the
globe, so distance between clinics means something. Around 8% are marked as not
accepting patients, which is the branch `create_appointment_atomic()` rejects.
- `random.seed()` and `Faker.seed()` are both fixed, so two people running this
against a fresh database get the same rows.



#### Verification

The script checks its own work before exiting and prints the result of each
check. It exits non-zero if any of them fail:

```
verifying...
  [ok] clinics: 250
  [ok] patients: 25000
  [ok] appointments (>= 50,000): 60000
  [ok] wallet_audit_logs (>= 100,000): 116655
  [ok] patients holding more than one open appointment: 0
  [ok] negative balances: 0
  [ok] audit rows with a non positive amount: 0
  [ok] patients whose latest audit row disagrees with hsa_balance: 0
  [ok] orphaned audit rows: 0
  ...  CREDIT: 41,556
  ...  DEBIT: 75,099
  ...  DISCHARGED: 54,000
  ...  IN_CONSULTATION: 2,973
  ...  WAITING: 3,027
  ...  ledger covers 2025-03-12 to 2026-09-03
```

The last balance check is the one worth reading. It goes to the newest audit row
for every patient and confirms its `balance_after` is the balance that patient
is actually sitting on, which is the only thing that makes the table a ledger
rather than a pile of numbers.

The script also runs `ANALYZE` and refreshes `clinic_monthly_discharges` on the
way out. The `ANALYZE` matters: without it the planner is still working off
empty-table statistics and any `EXPLAIN` taken straight after the load describes
a database that no longer exists.