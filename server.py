import json
import urllib.request
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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