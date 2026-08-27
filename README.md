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
- `03_nearest_mobile_nurse.js`

To add a sample test data for nurse pings you can run the following command (This is seeding script):
```bash
mongosh mongo/02_seed_nurse_pings.js
```
And then for retrieving the nearest active nurses you can run the following command (This is the script that uses `$geoNear` to retrieve the nearest active nurses that have pinged recently):
```bash
mongosh mongo/03_nearest_mobile_nurse.js
```
Also I have HARD-CODED current patient location, that you will be able to see in `03_nearest_mobile_nurse.js`\
\
You can add your test datas in this collection and run this retrieving script for more testing.