import math
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_reports = {}


class ReportRequest(BaseModel):
    user_id: str
    latitude: float
    longitude: float
    detection_type: str


def calculate_distance_meters(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_live_dpmz_buses():
    return [
        {
            "vehicle_id": "DPMZ_204",
            "line": "6",
            "lat": 49.2231,
            "lng": 18.7394,
            "heading": "Vlcince -> Hliny",
        },
        {
            "vehicle_id": "DPMZ_108",
            "line": "1",
            "lat": 49.2105,
            "lng": 18.7450,
            "heading": "Solinky -> Centrum",
        },
        {
            "vehicle_id": "DPMZ_312",
            "line": "4",
            "lat": 49.2200,
            "lng": 18.7550,
            "heading": "Vlcince -> Zavodie",
        },
    ]


@app.get("/", response_class=HTMLResponse)
def get_map():
    return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>MHD Radar Zilina</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>body { margin: 0; } #map { height: 100vh; }</style>
</head>
<body>
    <div id="map"></div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        const map = L.map('map').setView([49.2231, 18.7394], 14);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
        let markers = [];

        function load() {
            fetch('/map-data')
                .then(r => r.json())
                .then(buses => {
                    markers.forEach(m => map.removeLayer(m));
                    markers = [];
                    buses.forEach(b => {
                        let c = b.has_inspector ? 'red' : 'green';
                        let m = L.circleMarker([b.lat, b.lng], {color: c, fillColor: c, fillOpacity: 0.8, radius: 12}).addTo(map);
                        m.bindPopup('<b>Linka ' + b.line + '</b> (' + b.vehicle_id + ')<br>' + (b.has_inspector ? '🚨 REVÍZOR V SPOJI!' : '✅ V poriadku'));
                        markers.push(m);
                    });
                });
        }
        load();
        setInterval(load, 2000);
    </script>
</body>
</html>"""


@app.post("/report")
def report_inspector(report: ReportRequest):
    buses = get_live_dpmz_buses()
    matched = None
    min_d = 100
    for b in buses:
        d = calculate_distance_meters(
            report.latitude, report.longitude, b["lat"], b["lng"]
        )
        if d < min_d:
            min_d = d
            matched = b
    if not matched:
        raise HTTPException(status_code=404, detail="Bus not found")
    active_reports[matched["vehicle_id"]] = {
        "line": matched["line"],
        "vehicle_id": matched["vehicle_id"],
    }
    return {"status": "success"}


@app.get("/map-data")
def get_map_data():
    buses = get_live_dpmz_buses()
    for b in buses:
        b["has_inspector"] = b["vehicle_id"] in active_reports
    return buses


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)