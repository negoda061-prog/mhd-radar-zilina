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

# Databáza reálnych zastávok Žiliny s GPS súradnicami
STOPS = {
    "Matice slovenskej": (49.2135, 18.7630),
    "Fatranská": (49.2105, 18.7610),
    "Žilinská univerzita": (49.2052, 18.7558),
    "Pod hájom": (49.2008, 18.7490),
    "Jaseňová": (49.1985, 18.7430),
    "Limbová": (49.1995, 18.7390),
    "Smreková": (49.2020, 18.7360),
    "Hlinská": (49.2110, 18.7410),
    "Veľká okružná": (49.2200, 18.7390),
    "Železničná stanica": (49.2275, 18.7445),
    "Kvačalova, DPMŽ": (49.2250, 18.7200),
    "Hájik, Stodolova": (49.2190, 18.7180),
    "Považský Chlmec": (49.2435, 18.7350),
    "Bánová, Colnica": (49.1985, 18.7230),
}

# Definícia trasy a časov medzi zastávkami (v sekundách) pre hlavné linky
ROUTES_SCHEDULE = [
    {
        "line": "14",
        "stops": [
            STOPS["Matice slovenskej"],
            STOPS["Fatranská"],
            STOPS["Žilinská univerzita"],
            STOPS["Jaseňová"],
            STOPS["Smreková"],
            STOPS["Hlinská"],
            STOPS["Veľká okružná"],
            STOPS["Železničná stanica"],
        ],
    },
    {
        "line": "50",
        "stops": [
            STOPS["Matice slovenskej"],
            STOPS["Fatranská"],
            STOPS["Žilinská univerzita"],
            STOPS["Pod hájom"],
            STOPS["Limbová"],
            STOPS["Hlinská"],
            STOPS["Veľká okružná"],
        ],
    },
    {
        "line": "6",
        "stops": [
            STOPS["Hájik, Stodolova"],
            STOPS["Kvačalova, DPMŽ"],
            STOPS["Veľká okružná"],
            STOPS["Železničná stanica"],
            STOPS["Matice slovenskej"],
        ],
    },
    {
        "line": "21",
        "stops": [
            STOPS["Bánová, Colnica"],
            STOPS["Kvačalova, DPMŽ"],
            STOPS["Železničná stanica"],
            STOPS["Považský Chlmec"],
        ],
    },
]


def get_current_bus_positions():
    """Vypočíta presnú pozíciu autobusu medzi zastávkami na základe aktuálneho času."""
    current_time = time.time()
    buses = []

    for idx, route in enumerate(ROUTES_SCHEDULE):
        stops = route["stops"]
        num_stops = len(stops)
        time_per_segment = 40  # 40 sekúnd presun medzi zastávkami
        total_cycle_time = num_stops * time_per_segment

        # Posun pre viacero vozidiel na rovnakej linke
        progress = (current_time + (idx * 120)) % total_cycle_time
        current_segment = int(progress // time_per_segment)
        segment_progress = (progress % time_per_segment) / time_per_segment

        start_stop = stops[current_segment]
        end_stop = stops[(current_segment + 1) % num_stops]

        # Lineárna interpolácia GPS súradníc podľa času
        lat = start_stop[0] + (end_stop[0] - start_stop[0]) * segment_progress
        lng = start_stop[1] + (end_stop[1] - start_stop[1]) * segment_progress

        v_id = f"DPMZ-{route['line']}-{idx+1}"
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
        <title>MHD Radar Žilina - Živé spojenia DPMŽ</title>
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
                        data.forEach(bus => {
                            var color = bus.has_inspector ? '#e74c3c' : '#00b894';
                            var customIcon = L.divIcon({
                                className: 'custom-div-icon',
                                html: "<div style='background-color:" + color + ";width:24px;height:24px;border-radius:50%;border:2px solid white;box-shadow:0 0 6px rgba(0,0,0,0.4);display:flex;align-items:center;justify-content:center;color:white;font-size:11px;font-weight:bold;'>" + bus.line + "</div>",
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
    buses = get_current_bus_positions()
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
        raise HTTPException(
            status_code=404, detail="Nenašiel sa žiadny autobus v blízkosti"
        )

    active_reports[matched["vehicle_id"]] = True
    return {"status": "success"}


@app.get("/map-data")
def get_map_data():
    return get_current_bus_positions()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)