# SSD-A1-Project-4-CareConnect

## Workflow 3 – Nearest Mobile Nurse

### Overview

Workflow 3 uses MongoDB's `$geoNear` aggregation stage to locate the
nearest active mobile nurse to a patient's current coordinates.

The workflow operates on the `NursePings` collection in the
`careconnect_db` database.

### MongoDB Setup

The `NursePings` collection uses a `2dsphere` index on the `location`
field for geospatial queries.
That is already done in Step 2.

### NursePing Document Structure

Test NursePing documents use the following structure:

```javascript
{
    nurse_id: "N001",
    active: true,
    location: {
        type: "Point",
        coordinates: [longitude, latitude]
    },
    created_at: new Date()
}
```

Also we have two files for this workflow 3

- `02_seed_nurse_pings.js`
- `02_workflow3_geonear.js`

To add a sample test data for nurse pings you can run the following command (This is seeding script ONLY TO BE USED FOR LOCAL TESTING, AND NOT TO INCLUDE IN FINAL PROJECT):

```bash
mongosh mongo/02_seed_nurse_pings.js
```

And then for retrieving the nearest active nurses you can run the following command (This is the script that uses `$geoNear` to retrieve the nearest active nurses that have pinged recently):

```bash
mongosh mongo/02_workflow3_geonear.js
```

Also I have HARD-CODED current patient location, that you will be able to see in `02_workflow3_geonear.js`  

You can add your test datas in this collection and run this retrieving script for more testing.

---



## Workflow 4 – Multi-Faceted Review Analytics



### Overview

Workflow 4 uses MongoDB's `$facet` aggregation stage to simultaneously extract rating buckets, determine frequent sentiment tags using the `$unwind` operator, and calculate the global average rating across the platform.

The workflow operates on the `PatientReviews` collection in the `careconnect_db` database.

### MongoDB Setup

The `PatientReviews` collection utilizes standard indexes on fields like `clinic_id` and `rating` to optimize the aggregation pipeline operations. 

### PatientReview Document Structure

Test PatientReview documents use the following structure:

```javascript

{

    appointment_id: "A001",

    clinic_id: "C001",

    patient_id: "P001",

    rating: 5,

    bedside_manner_tags: ["empathetic", "punctual", "clear-instructions"],

    review_text: "Great experience.",

    created_at: new Date()

}
```



### Executing Workflow 4:

I have added two files for workflow 4:

- `03_seed_workflow4.js` (temporary, need to be removed before final submission)
- `03_workflow4_facet.js`

Run the following commands to test workflow 4:

```bash
mongosh mongo/03_seed_workflow4.js
mongosh mongo/03_workflow4_facet.js
```

---

