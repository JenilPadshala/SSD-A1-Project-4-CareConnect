import random
from datetime import datetime, timedelta
from pymongo import MongoClient
from faker import Faker
import uuid

# Configuration
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "careconnect_db"
BASE_LONGITUDE = 78.359518 # IIITH location
BASE_LATITUDE = 17.4532608

fake = Faker()

def clear_collections(db):
    """Wipes the target collections for a clean run."""
    print("Clearing existing data...")
    db["MedicalCatalogs"].delete_many({})
    db["PatientReviews"].delete_many({})
    db["NursePings"].delete_many({})

def seed_medical_catalogs(db, total_catalogs=1000):
    """Generates flexible medical catalogs."""
    print("Seeding MedicalCatalogs...")
    catalogs_col = db["MedicalCatalogs"]
    catalogs = []
    specialties = ["Cardiology", "Dermatology", "Pediatrics", "Neurology", "General Practice"]
    
    for _ in range(total_catalogs):
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
    print(f"  Inserted {len(catalogs)} documents into MedicalCatalogs.")

def seed_patient_reviews(db, total_reviews=100000, batch_size=10000):
    """Generates structured patient reviews in memory-safe batches."""
    print("Seeding PatientReviews (Batch processing)...")
    reviews_col = db["PatientReviews"]
    tags_pool = ["empathetic", "punctual", "clear-instructions", "rushed", "unprofessional", "friendly", "thorough"]
    
    for i in range(0, total_reviews, batch_size):
        batch = []
        for _ in range(batch_size):
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
        print(f"  Inserted {i + batch_size} / {total_reviews} reviews...")

def seed_nurse_pings(db, total_pings=500000, batch_size=10000):
    """Generates high-volume geospatial telemetry data for 5 nurses."""
    print("Seeding NursePings (Batch processing)...")
    pings_col = db["NursePings"]
    
    # Pre-generate exactly 5 unique nurse IDs
    nurse_ids = [f"N_{str(uuid.uuid4())[:8]}" for _ in range(5)]
    
    for i in range(0, total_pings, batch_size):
        batch = []
        for _ in range(batch_size):
            # Adding +/- 0.05 degrees of jitter creates a scatter roughly within a 5km radius
            lng = BASE_LONGITUDE + random.uniform(-0.05, 0.05)
            lat = BASE_LATITUDE + random.uniform(-0.05, 0.05)
            
            ping = {
                "nurse_id": random.choice(nurse_ids),
                "active": random.choice([True, False]),
                "location": {
                    "type": "Point",
                    "coordinates": [lng, lat]
                },
                "created_at": datetime.now() - timedelta(minutes=random.randint(0, 119)) # TTL window
            }
            batch.append(ping)
        
        pings_col.insert_many(batch)
        print(f"  Inserted {i + batch_size} / {total_pings} pings...")

def main():
    print(f"Connecting to MongoDB at {MONGO_URI}...")
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    
    clear_collections(db)
    seed_medical_catalogs(db)
    seed_patient_reviews(db)
    seed_nurse_pings(db)
    
    print("MongoDB seeding completed successfully!")
    client.close()

if __name__ == "__main__":
    main()