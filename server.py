import datetime
import math
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_reports = {}

# Súradnice hlavných uzlov Žiliny z tvojho zoznamu
STOPS = {
    "Zel_stanica": (49.2275, 18.7445),
    "Vlcince": (49.2135, 18.7630),
    "Solinky": (49.1985, 18.7430),
    "Hliny": (49.2110, 18.7410),
    "Zavodie": (49.2150, 18.7250),
    "Hajik": (49.2190, 18.7180),
    "Pov_Chlmec": (49.2435, 18.7350),
    "Banova": (49.1985, 18.7230),
}

# Trasa nočnej linky 50 podľa obrázka
NIGHT_LINE_50_STOPS = [
    STOPS["Zel_stanica"],
    STOPS["Vlcince"],
    STOPS["Solinky"],
    STOPS["Hliny"],
    STOPS["Zavodie"],
    STOPS["Hajik"],
]

# Denné linky z obrázka
DAY_ROUTES = [
    {"line": "1", "stops": [STOPS["Zel_stanica"], STOPS["Vlcince"]]},
    {"line": "3", "stops": [STOPS["Solinky"], STOPS["Hliny"]]},
    {"line": "4", "stops": [STOPS["Vlcince"], STOPS["Solinky"]]},
    {"line": "6", "stops": [STOPS["Hajik"], STOPS["Zavodie"], STOPS["Vlcince"]]},
    {
        "line": "14",
        "stops": [
            STOPS["Vlcince"],
            STOPS["Solinky"],
            STOPS["Hliny"],
            STOPS["Zel_stanica"],
        ],
    },
    {
        "line": "21",
        "stops": [STOPS["Banova"], STOPS["Zavodie"], STOPS["Pov_Chlmec"]],
    },
    {
        "line": "27",
        "stops": [STOPS["Hajik"], STOPS["Zel_stanica"], STOPS["Pov_Chlmec"]],
    },
]


def is_night_time():
    """Zistí, či je aktuálny čas v rozmedzí 22:55 až 04:50."""
    now = datetime.datetime.now().time()
    night_start = datetime.time(22, 55)
    night_end = datetime.time(4, 50)
    return now >= night_start or now <= night_end


def get_current_buses():
    current_time = time.time()
    buses = []

    if is_night_time():
        # NOČNÁ PREVÁDZKA: Len Linka 50
        num_stops = len(NIGHT_LINE_50_STOPS)
        time_per_segment = 60
        total_cycle = num_stops * time_per_segment

        for bus_idx in range(2):  # 2 nočné autobusy na linke 50
            progress = (current_time + (bus_idx * 180)) % total_cycle
            seg_idx = int(progress // time_per_segment)
            seg_progress = (progress % time_per_segment) / time_per_segment

            p1 = NIGHT_LINE_50_STOPS[seg_idx]
            p2 = NIGHT_LINE_50_STOPS[(seg_idx + 1) % num_stops]

            lat = p1[0] + (p2[0] - p1[0]) * seg_progress
            lng = p1[1] + (p2[1] - p1[1]) * seg_progress
            v_id = f"NIGHT-50-{bus_idx+1}"

            buses.append(
                {
                    "vehicle_id": v_id,
                    "line": "50",
                    "lat": round(lat, 6),
                    "lng": round(lng, 6),
                    "has_inspector": v_id in active_reports,
                }
            )
    else:
        # DENNÁ PREVÁDZKA: Bežné trolejbusy a autobusy
        for idx, route in enumerate(DAY_ROUTES):
            stops = route["stops"]
            num_stops = len(stops)
            time_per_segment = 45
            total_cycle = num_stops * time_per_segment

            progress = (current_time + (idx * 90)) % total_cycle
            seg_idx = int(progress // time_per_segment)
            seg_progress = (progress % time_per_segment) / time_per_segment

            p1 = stops[seg_idx]
            p2 = stops[(seg_idx + 1) % num_stops]

            lat = p1[0] + (p2[0] - p1[0]) * seg_progress
            lng = p1[1] + (p2[1] - p1[1]) * seg_progress
            v_id = f"DAY-{route['line']}-{idx+1}"

            buses.append(
                {
                    "vehicle_id": v_id,
                    "line": route["line"],
                    "lat": round(lat, 6),
                    "lng": round(lng, 6),
                    "has_inspector": v_id in active_reports,
                }
            )

    return buses


class ReportRequest(BaseModel):
    latitude: float
    longitude: float


@app.get("/", response_class=HTMLResponse)
def get_map_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MHD Radar Žilina</title>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            #map { height: 100vh; width: 100%; margin: 0; padding: 0; }
            body { margin: 0; font-family: Arial, sans-serif; }
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
            var map = L.map('map').setView([49.2231, 18.7394], 13);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19
            }).addTo(map);

            var markers = {};

            function updateMap() {
                fetch('/map-data')
                    .then(res => res.json())
                    .then(data => {
                        // Odstránenie starých značiek pri premene deň/noc
                        var currentIds = data.map(b => b.vehicle_id);
                        for (var id in markers) {
                            if (!currentIds.includes(id)) {
                                map.removeLayer(markers[id]);
                                delete markers[id];
                            }
                        }

                        data.forEach(bus => {
                            var color = bus.has_inspector ? '#e74c3c' : (bus.line === '50' ? '#8e44ad' : '#00b894');
                            var customIcon = L.divIcon({
                                className: 'custom-div-icon',
                                html: "<div style='background-color:" + color + ";width:24px;height:24px;border-radius:50%;border:2px solid white;box-shadow:0 0 6px rgba(0,0,0,0.4);display:flex;align-items:center;justify-content:center;color:white;font-size:10px;font-weight:bold;'>" + bus.line + "</div>",
                                iconSize: [26, 26]
                            });

                            if (markers[bus.vehicle_id]) {
                                markers[bus.vehicle_id].setLatLng([bus.lat, bus.lng]);
                            } else {
                                var m = L.marker([bus.lat, bus.lng], {icon: customIcon})
                                    .bindPopup("<b>Linka: " + bus.line + "</b><br>Vozidlo: " + bus.vehicle_id)
                                    .addTo(map);
                                markers[bus.vehicle_id] = m;
                            }
                        });
                    });
            }

            updateMap();
            setInterval(updateMap, 2000);
        </script>
    </body>
    </html>
    """


@app.post("/report")
def report_inspector(report: ReportRequest):
    buses = get_current_buses()
    matched = None
    min_d = 0.005

    for b in buses:
        d = math.sqrt(
            (report.latitude - b["lat"]) ** 2
            + (report.longitude - b["lng"]) ** 2
        )
        if d < min_d:
            min_d = d
            matched = b

    if not matched:
        raise HTTPException(status_code=404, detail="Autobus nebol v blízkosti")

    active_reports[matched["vehicle_id"]] = True
    return {"status": "success"}


@app.get("/map-data")
def get_map_data():
    return get_current_buses()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)