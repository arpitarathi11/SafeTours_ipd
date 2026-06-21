# seed_hexes.py
# Generates Mumbai H3 hexes + assigns crime scores
# Saves output locally as hex_scores.json

import h3
import json
from score_engine import calculate_base_score

# ----------------------------
# Full Mumbai bounds restored
# ----------------------------
MUMBAI_BOUNDS = {
    "lat_min": 18.89,
    "lat_max": 19.27,
    "lng_min": 72.77,
    "lng_max": 73.05,
}

H3_RESOLUTION = 9

# ----------------------------
# Sample incidents
# ----------------------------
SAMPLE_INCIDENTS = [
    {"lat": 19.0760, "lng": 72.8777, "severity": 0.6},
    {"lat": 19.0596, "lng": 72.8295, "severity": 0.4},
    {"lat": 19.1136, "lng": 72.8697, "severity": 0.3},
    {"lat": 19.1197, "lng": 72.9000, "severity": 0.7},
    {"lat": 18.9548, "lng": 72.8346, "severity": 0.5},
]


def get_mumbai_hexes():
    boundary = [
        (18.89, 72.77),
        (18.89, 73.05),
        (19.27, 73.05),
        (19.27, 72.77)
    ]

    hexes = h3.polygon_to_cells(
        boundary,
        [],
        H3_RESOLUTION
    )

    return set(hexes)


def aggregate_incidents_to_hexes(incidents):
    hex_data = {}

    for incident in incidents:
        hex_id = h3.latlng_to_cell(
            incident["lat"],
            incident["lng"],
            H3_RESOLUTION
        )

        if hex_id not in hex_data:
            hex_data[hex_id] = {
                "count": 0,
                "total_severity": 0
            }

        hex_data[hex_id]["count"] += 1
        hex_data[hex_id]["total_severity"] += incident["severity"]

    return hex_data


def save_to_json(all_hex_ids, hex_data):
    output = []
    total = len(all_hex_ids)

    print(f"Saving {total} hexes locally...")

    for i, hex_id in enumerate(all_hex_ids):

        if i % 100 == 0:
            print(f"Processed {i}/{total}")

        data = hex_data.get(
            hex_id,
            {
                "count": 0,
                "total_severity": 0
            }
        )

        count = data["count"]

        avg_severity = (
            data["total_severity"] / count
            if count > 0 else 0
        )

        result = calculate_base_score(count, avg_severity)

        lat, lng = h3.cell_to_latlng(hex_id)

        output.append({
            "hex_id": hex_id,
            "lat": lat,
            "lng": lng,
            "base_score": result["score"],
            "zone": result["zone"],
            "crime_count": count,
            "crime_severity": round(avg_severity, 3)
        })

    with open("hex_scores.json", "w") as f:
        json.dump(output, f, indent=2)

    print("Done!")
    print("Saved file: hex_scores.json")


if __name__ == "__main__":
    print("Step 1: Generating Mumbai hexes...")
    all_hexes = get_mumbai_hexes()
    print(f"Found {len(all_hexes)} hexes")

    print("Step 2: Mapping incidents...")
    hex_data = aggregate_incidents_to_hexes(SAMPLE_INCIDENTS)
    print(f"{len(hex_data)} hexes contain incidents")

    print("Step 3: Saving data...")
    save_to_json(all_hexes, hex_data)