db = db.getSiblingDB("careconnect_db");
db.NursePings.deleteMany({});

db.NursePings.insertMany([
    {
        nurse_id: "N001",
        active: true,
        location: {
            type: "Point",
            coordinates: [17.4002426,78.4254062]
        },
        created_at: new Date()
    },
    {
        nurse_id: "N002",
        active: false,
        location: {
            type: "Point",
            coordinates: [17.3994126,78.4222058]
        },
        created_at: new Date()
    },
    {
        nurse_id: "N003",
        active: true,
        location: {
            type: "Point",
            coordinates: [17.4126084,78.2428932]
        },
        created_at: new Date()
    },
    {
        nurse_id: "N004",
        active: true,
        location: {
            type: "Point",
            coordinates: [17.4126084,78.2428932]
        },
        created_at: new Date()
    },
    {
        nurse_id: "N004",
        active: true,
        location: {
            type: "Point",
            coordinates: [22.8494385,74.2319361]
        },
        created_at: new Date()
    },
    {
        nurse_id: "N005",
        active: false,
        location: {
            type: "Point",
            coordinates: [23.0204737,72.4145907]
        },
        created_at: new Date()
    },
]);

print("NursePing test data seeded successfully!");