import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
from zoneinfo import ZoneInfo

INFO_URL = "https://gbfs.citibikenyc.com/gbfs/en/station_information.json"
STATUS_URL = "https://gbfs.citibikenyc.com/gbfs/en/station_status.json"

OUTPUT = Path("midtown_snapshots.csv")

def fetch(url):
    with urlopen(url, timeout=30) as response:
        return json.load(response)["data"]["stations"]

info = fetch(INFO_URL)
status = fetch(STATUS_URL)

status_by_id = {
    str(s["station_id"]): s for s in status
}

now = datetime.now(timezone.utc)
ny_time = now.astimezone(ZoneInfo("America/New_York"))

rows = []

for station in info:
    lat = station["lat"]
    lon = station["lon"]

    # Approximate Midtown study area
    if not (40.735 <= lat <= 40.769):
        continue
    if not (-74.012 <= lon <= -73.958):
        continue

    s = status_by_id.get(str(station["station_id"]))

    if s is None:
        continue

    docks = s.get("num_docks_available")
    reported = s.get("last_reported")

    fresh = (
        isinstance(reported, (int, float))
        and 0 <= now.timestamp() - reported <= 900
    )

    valid = (
        fresh
        and s.get("is_installed") == 1
        and s.get("is_returning") == 1
        and isinstance(docks, int)
    )

    rows.append({
        "snapshot_time": ny_time.isoformat(),
        "station_id": station["station_id"],
        "station_name": station["name"],
        "latitude": lat,
        "longitude": lon,
        "capacity": station.get("capacity"),
        "docks_available": docks,
        "bikes_available": s.get("num_bikes_available"),
        "is_returning": s.get("is_returning"),
        "last_reported": reported,
        "valid": int(valid),
        "full": int(docks == 0) if valid else ""
    })

if not rows:
    raise RuntimeError("No Midtown stations found")

exists = OUTPUT.exists() and OUTPUT.stat().st_size > 0

with OUTPUT.open("a", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=rows[0].keys())

    if not exists:
        writer.writeheader()

    writer.writerows(rows)

print(f"Collected {len(rows)} Midtown-area stations at {ny_time}")
print(f"Saved to {OUTPUT}")
