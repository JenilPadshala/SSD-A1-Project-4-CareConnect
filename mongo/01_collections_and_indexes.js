// connect to database
db = db.getSiblingDB('careconnect_db');

// create collections
db.createCollection("MedicalCatalogs");
db.createCollection("PatientReviews");
db.createCollection("NursePings");


print("CareConnect MongoDB collections successfully initialized.");