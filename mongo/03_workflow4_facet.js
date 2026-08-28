db = db.getSiblingDB("careconnect_db");

const reviewAnalytics = db.PatientReviews.aggregate([
    {
        $facet: {
            "rating_distribution": [
                {
                    $bucket: {
                        groupBy: "$rating",
                        boundaries: [1, 2, 3, 4, 5, 6], 
                        default: "Unknown",
                        output: { count: { $sum: 1 } }
                    }
                }
            ],
            "frequent_tags": [
                { $unwind: "$bedside_manner_tags" },
                { $group: { _id: "$bedside_manner_tags", frequency: { $sum: 1 } } },
                { $sort: { frequency: -1 } },
                { $limit: 5 }
            ],
            "global_average": [
                {
                    $group: {
                        _id: null, 
                        average_rating: { $avg: "$rating" },
                        total_reviews: { $sum: 1 }
                    }
                }
            ]
        }
    }
]).toArray();

print("\n--- Workflow 4: Multi-Faceted Review Analytics ---");
printjson(reviewAnalytics);