// 17.4532608,78.359518
db = db.getSiblingDB("careconnect_db");
const patientLocation = {
    type: "Point",
    coordinates: [17.4532608,78.359518]
};

const nearNurses = db.NursePings.aggregate([
    {
        $geoNear:{
            near:patientLocation,
            key:"location",
            distanceField:"distance",
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