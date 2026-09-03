// 17.4532608,78.359518
db = db.getSiblingDB("careconnect_db");
// Patient location (fixed)
const patientLocation = {
    type: "Point",
    coordinates: [78.359518, 17.4532608] // [Longitude, Latitude]
};

const nearNurses = db.NursePings.aggregate([
    {
        $geoNear:{
            near:patientLocation,
            key:"location",
            distanceField:"distance",
            maxDistance:5000,
            query:{
                active:true
            },
            spherical:true
        }
    },
    {
        $limit:1
    }
]).toArray();

if(nearNurses.length ===0){
    print("No active Nurse found");
}else{
    nearNurses.forEach(nurse => printjson(nurse));
}