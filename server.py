import json
import urllib.request
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


class ReportRequest(BaseModel):
    latitude: float
    longitude: float


def get_live_dpmz_buses():
    url = "https://www.dpmz.sk/api/vehicles/"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            buses = []
            for item in data.get("vehicles", []):
                buses.append(
                    {
                        "vehicle_id": str(item.get("id")),
                        "line": str(item.get("line_name", "?")),
                        "lat": float(item.get("lat")),
                        "lng": float(item.get("lng")),
                    }
                )
            return buses
    except Exception as e:
        print(f"Chyba pri stahovani DPMZ API: {e}")
        return []


def calculate_distance_meters(lat1, lon1, lat2, lon2):
    return (((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2) ** 0.5) * 111000


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
                            var color = bus.has_inspector ? 'red' : 'green';
                            var customIcon = L.divIcon({
                                className: 'custom-div-icon',
                                html: "<div style='background-color:" + color + ";width:16px;height:16px;border-radius:50%;border:2px solid white;'></div>",
                                iconSize: [20, 20]
                            });

                            if (markers[bus.vehicle_id]) {
                                markers[bus.vehicle_id].setLatLng([bus.lat, bus.lng]);
                            } else {
                                var m = L.marker([bus.lat, bus.lng], {icon: customIcon})
                                    .bindPopup("<b>Linka: " + bus.line + "</b><br>ID: " + bus.vehicle_id)
                                    .addTo(map);
                                markers[bus.vehicle_id] = m;
                            }
                        });
                    });
            }

            updateMap();
            setInterval(updateMap, 5000);
        </script>
    </body>
    </html>
    """


@app.post("/report")
def report_inspector(report: ReportRequest):
    buses = get_live_dpmz_buses()
    matched = None
    min_d = 200
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
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)