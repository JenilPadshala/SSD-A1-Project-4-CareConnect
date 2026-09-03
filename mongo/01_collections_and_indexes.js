// connect to database
db = db.getSiblingDB('careconnect_db');

// create collections
db.createCollection("MedicalCatalogs");
db.createCollection("PatientReviews");
db.createCollection("NursePings");

// create the Geospatial Index for the location field
db.NursePings.createIndex({ "location": "2dsphere" });

// create the Time-To-Live (TTL) Index with 2 hours expiration
db.NursePings.createIndex(
    { "created_at": 1 },
    { expireAfterSeconds: 7200 }
);

print("CareConnect MongoDB collections successfully initialized.");