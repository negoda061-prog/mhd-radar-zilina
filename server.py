import math
import random
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

# Zoznam reálnych liniek Žiliny (vrátane linky 50)
LINES_DATA = [
    {"line": "50", "lat": 49.2150, "lng": 18.7450},
    {"line": "50", "lat": 49.2280, "lng": 18.7300},
    {"line": "1", "lat": 49.2020, "lng": 18.7400},
    {"line": "3", "lat": 49.2100, "lng": 18.7600},
    {"line": "4", "lat": 49.2350, "lng": 18.7450},
    {"line": "6", "lat": 49.2050, "lng": 18.7300},
    {"line": "7", "lat": 49.2200, "lng": 18.7500},
    {"line": "14", "lat": 49.2400, "lng": 18.7150},
    {"line": "21", "lat": 49.2250, "lng": 18.7700},
    {"line": "27", "lat": 49.1980, "lng": 18.7480},
]

buses_db = []
for i, item in enumerate(LINES_DATA):
    buses_db.append(
        {
            "vehicle_id": str(101 + i),
            "line": item["line"],
            "lat": item["lat"] + random.uniform(-0.005, 0.005),
            "lng": item["lng"] + random.uniform(-0.005, 0.005),
        }
    )


class ReportRequest(BaseModel):
    latitude: float
    longitude: float


def update_bus_positions():
    t = time.time()
    for b in buses_db:
        speed = 0.0001
        b["lat"] += math.sin(t + int(b["vehicle_id"])) * speed
        b["lng"] += math.cos(t + int(b["vehicle_id"])) * speed


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
            body { margin: 0; }
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
                            var color = bus.has_inspector ? '#e74c3c' : '#2ecc71';
                            var customIcon = L.divIcon({
                                className: 'custom-div-icon',
                                html: "<div style='background-color:" + color + ";width:22px;height:22px;border-radius:50%;border:2px solid white;box-shadow:0 0 5px rgba(0,0,0,0.4);display:flex;align-items:center;justify-content:center;color:white;font-size:11px;font-weight:bold;'>" + bus.line + "</div>",
                                iconSize: [24, 24]
                            });

                            if (markers[bus.vehicle_id]) {
                                markers[bus.vehicle_id].setLatLng([bus.lat, bus.lng]);
                            } else {
                                var m = L.marker([bus.lat, bus.lng], {icon: customIcon})
                                    .bindPopup("<b>Linka: " + bus.line + "</b><br>Vozidlo ID: " + bus.vehicle_id)
                                    .addTo(map);
                                markers[bus.vehicle_id] = m;
                            }
                        });
                    });
            }

            updateMap();
            setInterval(updateMap, 3000);
        </script>
    </body>
    </html>
    """


@app.post("/report")
def report_inspector(report: ReportRequest):
    update_bus_positions()
    matched = None
    min_d = 0.005
    for b in buses_db:
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
    update_bus_positions()
    res = []
    for b in buses_db:
        item = b.copy()
        item["has_inspector"] = b["vehicle_id"] in active_reports
        res.append(item)
    return res


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)