"""
bulk loader for the postgresql side of careconnect.

it fills clinics, patients, appointments and wallet_audit_logs with enough rows
to make the indexes and the analytics queries actually work for their living:

    100,000+ wallet ledger entries
     50,000+ appointments

the ledger is generated as a chain per patient rather than as independent rows,
so balance_after really does follow from the movement before it and the last
entry for a patient matches that patient's hsa_balance. a flat pile of random
amounts would load just as fast but every balance in it would be a lie, and the
audit table is the one place in this schema where that matters.

usage:

    pip install -r data_generation/requirements.txt
    createdb careconnect
    psql -d careconnect -f sql/01_schema_ddl.sql
    psql -d careconnect -f sql/02_indexes.sql
    psql -d careconnect -f sql/03_triggers_and_audit.sql
    psql -d careconnect -f sql/05_materialized_views.sql
    python data_generation/postgres_seeder.py

point it somewhere else with CARECONNECT_DSN, e.g.

    CARECONNECT_DSN="dbname=careconnect host=localhost user=postgres" \
        python data_generation/postgres_seeder.py
"""

import csv
import io
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2.extras import execute_values
from faker import Faker

DSN = os.environ.get("CARECONNECT_DSN", "dbname=careconnect")

# fixed seed so two people running this get the same database
SEED = 20250401

CLINIC_COUNT = 250
PATIENT_COUNT = 25_000
APPOINTMENT_COUNT = 60_000

# appointments still open. the partial unique index in 02_indexes.sql allows
# only one WAITING/IN_CONSULTATION row per patient, so these go to distinct
# patients and the count has to stay under PATIENT_COUNT.
OPEN_APPOINTMENTS = 6_000

# floor for the bulk loaded part of the ledger. the live phase further down
# adds a few thousand more on top through the audit trigger.
LEDGER_ROWS = 100_000
LIVE_MOVEMENTS = 4_000

# how far back the history goes
HISTORY_DAYS = 540

COPY_BATCH = 20_000

# copays in cents. avoids the rounding drift you get from adding floats
# together a few hundred thousand times.
COPAY_CENTS = [1500, 2000, 2500, 3000, 4000, 5000, 7500, 10000, 12500, 15000,
               17500, 20000, 25000, 30000]

# clinics are scattered around a handful of metros rather than the whole globe,
# otherwise the geo side of the project has nothing sensible to sort by
METROS = [
    ("Hyderabad", 17.3850, 78.4867),
    ("Mumbai", 19.0760, 72.8777),
    ("Delhi", 28.6139, 77.2090),
    ("Bengaluru", 12.9716, 77.5946),
    ("Chennai", 13.0827, 80.2707),
    ("Kolkata", 22.5726, 88.3639),
    ("Pune", 18.5204, 73.8567),
    ("Ahmedabad", 23.0225, 72.5714),
]

CLINIC_KINDS = ["Family Clinic", "Urgent Care", "Health Center", "Medical Group",
                "Community Clinic", "Care Centre", "Wellness Clinic",
                "Primary Care", "Walk-In Clinic"]

random.seed(SEED)
Faker.seed(SEED)
fake = Faker()

NOW = datetime.now(timezone.utc)
HISTORY_START = NOW - timedelta(days=HISTORY_DAYS)


def money(cents):
    """cents to the string form the numeric(10,2) columns want."""
    return f"{cents // 100}.{cents % 100:02d}"


def copy_rows(cur, table, columns, rows, label):
    """
    load rows with COPY instead of INSERT. csv format rather than the default
    text format so a name with a comma or a quote in it survives the trip.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    sent = 0
    sql = f"COPY {table} ({', '.join(columns)}) FROM STDIN WITH (FORMAT csv)"

    for row in rows:
        writer.writerow(row)
        sent += 1
        if sent % COPY_BATCH == 0:
            buf.seek(0)
            cur.copy_expert(sql, buf)
            buf = io.StringIO()
            writer = csv.writer(buf)
            print(f"  {label}: {sent:,} rows")

    if buf.tell():
        buf.seek(0)
        cur.copy_expert(sql, buf)
    print(f"  {label}: {sent:,} rows (done)")
    return sent


def random_time(start, end):
    span = int((end - start).total_seconds())
    return start + timedelta(seconds=random.randrange(span))


def build_clinics():
    clinics = []
    for _ in range(CLINIC_COUNT):
        _city, lat, lon = random.choice(METROS)
        clinics.append((
            str(uuid.uuid4()),
            f"{fake.last_name()} {random.choice(CLINIC_KINDS)}",
            # roughly a 30km box around the city centre
            round(lat + random.uniform(-0.35, 0.35), 6),
            round(lon + random.uniform(-0.35, 0.35), 6),
            # a few clinics are closed to new patients, which is what
            # create_appointment_atomic() is supposed to reject
            random.random() > 0.08,
        ))
    return clinics


def build_ledger(patient_ids):
    """
    walk each patient forward through their own movements.

    returns the audit rows and the balance each patient ends the bulk load on.
    the balance is what goes into patients.hsa_balance, so the two tables agree
    with each other before the live phase touches anything.
    """
    # every patient gets a few movements. the top up loop only matters on an
    # unlucky draw, but it is what actually guarantees the 100k floor.
    movements = [random.randint(3, 6) for _ in patient_ids]
    while sum(movements) < LEDGER_ROWS:
        movements[random.randrange(len(movements))] += 1

    smallest_copay = min(COPAY_CENTS)
    rows = []
    balances = {}

    for patient_id, count in zip(patient_ids, movements):
        balance = random.randrange(20_000, 500_000)   # opening balance in cents

        # one timestamp per movement, then replayed oldest first so
        # balance_after climbs and falls in the order the dates suggest
        stamps = sorted(random_time(HISTORY_START, NOW - timedelta(days=2))
                        for _ in range(count))

        for stamp in stamps:
            # a debit can never take the balance under zero, the CHECK on
            # patients.hsa_balance would not allow the matching balance either
            if balance < smallest_copay or random.random() < 0.35:
                amount = random.randrange(2_500, 25_000)
                action = "CREDIT"
                balance += amount
            else:
                amount = min(random.choice(COPAY_CENTS), balance)
                action = "DEBIT"
                balance -= amount

            rows.append((
                str(uuid.uuid4()),
                patient_id,
                money(amount),
                action,
                money(balance),
                stamp.isoformat(),
            ))

        balances[patient_id] = balance

    return rows, balances


def build_appointments(patient_ids, clinic_ids):
    """
    open appointments go to distinct patients so the partial unique index in
    02_indexes.sql is happy, and they are all recent because an appointment
    that has been WAITING since last spring is not a real appointment.
    """
    appointments = []
    open_patients = random.sample(patient_ids, OPEN_APPOINTMENTS)

    for patient_id in open_patients:
        appointments.append((
            str(uuid.uuid4()),
            patient_id,
            random.choice(clinic_ids),
            money(random.choice(COPAY_CENTS)),
            random.choice(["WAITING", "IN_CONSULTATION"]),
            random_time(NOW - timedelta(days=2), NOW).isoformat(),
        ))

    for _ in range(APPOINTMENT_COUNT - OPEN_APPOINTMENTS):
        appointments.append((
            str(uuid.uuid4()),
            random.choice(patient_ids),
            random.choice(clinic_ids),
            money(random.choice(COPAY_CENTS)),
            "DISCHARGED",
            random_time(HISTORY_START, NOW - timedelta(days=2)).isoformat(),
        ))

    random.shuffle(appointments)
    return appointments


def replay_through_trigger(cur, balances):
    """
    the rows above were written straight into wallet_audit_logs, which is fast
    but skips the trigger from 03_triggers_and_audit.sql entirely. so the last
    slice of the ledger is put through the real path instead: update the
    balance and let the trigger write the audit row.

    doing it as batched UPDATE ... FROM (VALUES ...) keeps it to a handful of
    statements rather than four thousand round trips.
    """
    patients = random.sample(list(balances), LIVE_MOVEMENTS)
    written = 0

    for start in range(0, len(patients), 1_000):
        chunk = patients[start:start + 1_000]
        payload = []

        for patient_id in chunk:
            balance = balances[patient_id]
            if balance < 30_000 or random.random() < 0.4:
                delta = random.randrange(2_500, 25_000)
            else:
                delta = -random.choice(COPAY_CENTS)
            balances[patient_id] = balance + delta
            sign = "-" if delta < 0 else ""
            payload.append((patient_id, sign + money(abs(delta))))

        # page_size has to cover the whole chunk, otherwise psycopg2 quietly
        # splits it and cur.rowcount only reports the last slice
        execute_values(cur, """
            UPDATE patients p
               SET hsa_balance = p.hsa_balance + v.delta::numeric(10,2)
              FROM (VALUES %s) AS v(id, delta)
             WHERE p.id = v.id::uuid
        """, payload, page_size=len(payload))
        written += cur.rowcount

    return written


def check(cur, description, sql, expected=None):
    cur.execute(sql)
    actual = cur.fetchone()[0]
    if expected is None:
        ok = True
    elif callable(expected):
        ok = expected(actual)
    else:
        ok = actual == expected
    print(f"  [{'ok' if ok else 'FAIL'}] {description}: {actual}")
    return ok


def verify(cur):
    print("\nverifying...")
    results = [
        check(cur, "clinics", "SELECT count(*) FROM clinics", CLINIC_COUNT),
        check(cur, "patients", "SELECT count(*) FROM patients", PATIENT_COUNT),
        check(cur, "appointments (>= 50,000)",
              "SELECT count(*) FROM appointments",
              lambda n: n >= 50_000),
        check(cur, "wallet_audit_logs (>= 100,000)",
              "SELECT count(*) FROM wallet_audit_logs",
              lambda n: n >= 100_000),

        # the partial unique index should make this impossible, so it is really
        # a check that the index is installed at all
        check(cur, "patients holding more than one open appointment", """
            SELECT count(*) FROM (
                SELECT patient_id FROM appointments
                 WHERE status IN ('WAITING', 'IN_CONSULTATION')
                 GROUP BY patient_id HAVING count(*) > 1
            ) x
        """, 0),

        check(cur, "negative balances",
              "SELECT count(*) FROM patients WHERE hsa_balance < 0", 0),
        check(cur, "audit rows with a non positive amount",
              "SELECT count(*) FROM wallet_audit_logs WHERE amount_changed <= 0", 0),

        # the one that actually proves the ledger is a ledger: the newest
        # balance_after on record has to be the balance the patient is sitting
        # on right now
        check(cur, "patients whose latest audit row disagrees with hsa_balance", """
            SELECT count(*)
              FROM patients p
              JOIN LATERAL (
                    SELECT balance_after
                      FROM wallet_audit_logs w
                     WHERE w.patient_id = p.id
                     ORDER BY w.timestamp DESC, w.id DESC
                     LIMIT 1
                   ) latest ON TRUE
             WHERE latest.balance_after <> p.hsa_balance
        """, 0),

        check(cur, "orphaned audit rows", """
            SELECT count(*) FROM wallet_audit_logs w
             WHERE NOT EXISTS (SELECT 1 FROM patients p WHERE p.id = w.patient_id)
        """, 0),
    ]

    cur.execute("""
        SELECT action_type, count(*)
          FROM wallet_audit_logs
         GROUP BY action_type ORDER BY action_type
    """)
    for action, count in cur.fetchall():
        print(f"  ...  {action}: {count:,}")

    cur.execute("""
        SELECT status, count(*)
          FROM appointments
         GROUP BY status ORDER BY status
    """)
    for status, count in cur.fetchall():
        print(f"  ...  {status}: {count:,}")

    cur.execute("SELECT min(timestamp)::date, max(timestamp)::date FROM wallet_audit_logs")
    first, last = cur.fetchone()
    print(f"  ...  ledger covers {first} to {last}")

    return all(results)


def main():
    print(f"connecting to: {DSN}")
    conn = psycopg2.connect(DSN)
    conn.autocommit = False
    cur = conn.cursor()

    # cascade because appointments and wallet_audit_logs both point at patients
    print("clearing existing rows...")
    cur.execute("TRUNCATE wallet_audit_logs, appointments, patients, clinics CASCADE")

    print("generating clinics...")
    clinics = build_clinics()
    copy_rows(cur, "clinics",
              ("id", "name", "latitude", "longitude", "is_accepting_patients"),
              clinics, "clinics")
    clinic_ids = [c[0] for c in clinics]

    print("generating patients and their wallet history...")
    patient_ids = [str(uuid.uuid4()) for _ in range(PATIENT_COUNT)]
    ledger, balances = build_ledger(patient_ids)

    copy_rows(cur, "patients", ("id", "name", "hsa_balance"),
              ((pid, fake.name(), money(balances[pid])) for pid in patient_ids),
              "patients")

    copy_rows(cur, "wallet_audit_logs",
              ("id", "patient_id", "amount_changed", "action_type",
               "balance_after", "timestamp"),
              ledger, "wallet_audit_logs")

    print("generating appointments...")
    copy_rows(cur, "appointments",
              ("id", "patient_id", "clinic_id", "copay_amount", "status", "created_at"),
              build_appointments(patient_ids, clinic_ids), "appointments")

    print("replaying recent movements through the audit trigger...")
    live = replay_through_trigger(cur, balances)
    print(f"  {live:,} balance updates, each one logged by the trigger")

    conn.commit()

    # the planner is working off empty table stats until this runs, which makes
    # any EXPLAIN taken straight after the load useless
    print("running ANALYZE...")
    cur.execute("ANALYZE clinics, patients, appointments, wallet_audit_logs")

    print("refreshing clinic_monthly_discharges...")
    cur.execute("SELECT refresh_clinic_discharges_mv()")
    conn.commit()

    ok = verify(cur)

    cur.close()
    conn.close()

    if not ok:
        raise SystemExit("seeding finished but some checks failed, see above")
    print("\nall checks passed.")


if __name__ == "__main__":
    main()
