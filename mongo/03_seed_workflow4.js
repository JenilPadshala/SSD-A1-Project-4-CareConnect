db = db.getSiblingDB("careconnect_db");
db.PatientReviews.deleteMany({});

db.PatientReviews.insertMany([
    {
        appointment_id: "A001",
        clinic_id: "C001",
        patient_id: "P001",
        rating: 5,
        bedside_manner_tags: ["empathetic", "punctual", "clear-instructions"],
        review_text: "Great experience.",
        created_at: new Date()
    },
    {
        appointment_id: "A002",
        clinic_id: "C001",
        patient_id: "P002",
        rating: 4,
        bedside_manner_tags: ["punctual", "friendly"],
        review_text: "Good, but slight wait.",
        created_at: new Date()
    },
    {
        appointment_id: "A003",
        clinic_id: "C002",
        patient_id: "P003",
        rating: 1,
        bedside_manner_tags: ["rushed", "unprofessional"],
        review_text: "Nurse was very late and rushed.",
        created_at: new Date()
    },
    {
        appointment_id: "A004",
        clinic_id: "C003",
        patient_id: "P004",
        rating: 5,
        bedside_manner_tags: ["empathetic", "thorough"],
        review_text: "Very attentive care.",
        created_at: new Date()
    },
    {
        appointment_id: "A005",
        clinic_id: "C002",
        patient_id: "P005",
        rating: 3,
        bedside_manner_tags: ["friendly", "rushed"],
        review_text: "Okay, but felt a bit hurried.",
        created_at: new Date()
    }
]);

print("PatientReviews test data seeded successfully!");