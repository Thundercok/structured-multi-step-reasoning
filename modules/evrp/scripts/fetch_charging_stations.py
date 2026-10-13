import json
import csv
import os
import urllib.request
import urllib.parse

def fetch_and_clean():
    os.makedirs("data", exist_ok=True)
    raw_path = os.path.join("data", "vietnam_charging_stations_raw.json")
    json_path = os.path.join("data", "vietnam_charging_stations.json")
    csv_path = os.path.join("data", "vietnam_charging_stations.csv")

    query = """
    [out:json][timeout:90];
    area["ISO3166-1"="VN"]->.searchArea;
    (
      node["amenity"="charging_station"](area.searchArea);
      way["amenity"="charging_station"](area.searchArea);
    );
    out center tags;
    """

    print("Fetching EV charging stations from OpenStreetMap (Overpass API)...")
    url = "https://overpass-api.de/api/interpreter"
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "EVRPOptimizer/1.0"})

    with urllib.request.urlopen(req) as resp:
        content = resp.read().decode("utf-8")
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(content)

    osm_data = json.loads(content)
    elements = osm_data.get("elements", [])
    records = []

    for el in elements:
        osm_id = el.get("id")
        osm_type = el.get("type")
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")

        tags = el.get("tags", {})
        operator = tags.get("operator") or tags.get("brand") or tags.get("operator:type") or "Unknown"
        name = tags.get("name") or tags.get("name:en") or f"Trạm sạc {operator}"
        brand = tags.get("brand") or tags.get("brand:wikidata") or operator

        socket_types = [
            f"{k.split(':', 1)[1]}:{v}" for k, v in tags.items() if k.startswith("socket:")
        ]

        addr_parts = [
            tags.get("addr:housenumber"),
            tags.get("addr:street"),
            tags.get("addr:subdistrict"),
            tags.get("addr:district"),
            tags.get("addr:city") or tags.get("addr:province"),
        ]
        address = ", ".join([p for p in addr_parts if p])

        records.append({
            "id": osm_id,
            "osm_type": osm_type,
            "lat": lat,
            "lon": lon,
            "name": name,
            "operator": operator,
            "brand": brand,
            "capacity": tags.get("capacity") or tags.get("capacity:motorcar") or "",
            "socket_types": "; ".join(socket_types) if socket_types else tags.get("socket", ""),
            "opening_hours": tags.get("opening_hours", ""),
            "fee": tags.get("fee", ""),
            "address": address,
            "website": tags.get("website", ""),
        })

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    fieldnames = [
        "id", "osm_type", "lat", "lon", "name", "operator", "brand",
        "capacity", "socket_types", "opening_hours", "fee", "address", "website"
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"Successfully processed {len(records)} charging stations.")
    print(f"Saved: {json_path}")
    print(f"Saved: {csv_path}")

if __name__ == "__main__":
    fetch_and_clean()
