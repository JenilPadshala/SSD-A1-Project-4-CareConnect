import random
from datetime import datetime, timedelta
from pymongo import MongoClient
from faker import Faker
import uuid

# initialize faker and mongodb client
fake = Faker()
client = MongoClient("mongodb://localhost:27017/")
db = client["careconnect_db"]

# collections
catalogs_col = db["MedicalCatalogs"]
reviews_col = db["PatientReviews"]

# clear existing data
catalogs_col.delete_many({})
reviews_col.delete_many({})

print("Seeding MedicalCatalogs...")
catalogs = []
specialties = ["Cardiology", "Dermatology", "Pediatrics", "Neurology", "General Practice"]
for _ in range(1000):
    catalog = {
        "clinic_id": str(uuid.uuid4()),
        "specialist_name": fake.name(),
        "specialty": random.choice(specialties),
        "availability": [
            {"day": "Monday", "slots": ["09:00-12:00", "14:00-17:00"]},
            {"day": "Wednesday", "slots": ["10:00-13:00"]}
        ],
        "medications_handled": [
            {"name": fake.color_name() + "cillin", "dosage_forms": ["10mg", "20mg"], "requires_rx": True}
        ]
    }
    catalogs.append(catalog)
catalogs_col.insert_many(catalogs)
print(f"Inserted {len(catalogs)} documents into MedicalCatalogs.")

print("Seeding PatientReviews (Batch processing)...")
tags_pool = ["empathetic", "punctual", "clear-instructions", "rushed", "unprofessional", "friendly", "thorough"]
total_reviews = 100000
batch_size = 10000

for i in range(0, total_reviews, batch_size):
    batch = []
    for _ in range(batch_size):
        # Generate random date within the last year
        random_days = random.randint(0, 365)
        created_date = datetime.now() - timedelta(days=random_days)
        
        review = {
            "appointment_id": str(uuid.uuid4()),
            "clinic_id": str(uuid.uuid4()),
            "patient_id": str(uuid.uuid4()),
            "rating": random.randint(1, 5),
            "bedside_manner_tags": random.sample(tags_pool, k=random.randint(1, 3)),
            "review_text": fake.sentence(),
            "created_at": created_date
        }
        batch.append(review)
    
    reviews_col.insert_many(batch)
    print(f"Inserted {i + batch_size} / {total_reviews} reviews...")

print("MongoDB seeding completed successfully!")