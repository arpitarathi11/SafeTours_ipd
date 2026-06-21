"""
rebuild_hex_crime.py  — v2
─────────────────────────────────────────────────────────────────────────────
Rebuilds crime_count and crime_severity for every hex cell in
hex_scores_enriched.json using real region-level data from:

    Praja Foundation — "State of Policing and Law and Order in Mumbai 2023"
    Source: RTI data from Mumbai Police, 2022 figures

Region-wise reported crimes (2022), Table 3:
    West    → 18,999 cases
    North   → 15,684 cases
    Central → 14,289 cases
    East    → 11,576 cases
    South   →  9,590 cases

East region density split:
    East is geographically large but crime concentrates in the western pocket
    (Govandi, Mankhurd, Chembur, Ghatkopar — lng < 72.930).
    The eastern portion is Trombay industrial zone + mangroves — near-zero population.
    85% of East crimes → East_dense pocket.
    15% of East crimes → East_sparse (industrial/mangrove fringe).

Run from safety-backend/:
    python rebuild_hex_crime.py

Input:  hex_scores_enriched.json
Output: hex_scores_enriched.json (timestamped backup created first)
"""

import json
import shutil
from datetime import datetime

REGION_CRIME_DATA = {
    "West": {
        "total_crimes": 18999,
        "severity": 0.72,
    },
    "North": {
        "total_crimes": 15684,
        "severity": 0.65,
    },
    "Central": {
        "total_crimes": 14289,
        "severity": 0.68,
    },
    "East_dense": {
        # Govandi, Mankhurd, Chembur, Ghatkopar — 85% of East crimes
        "total_crimes": round(11576 * 0.85),
        "severity": 0.82,
    },
    "East_sparse": {
        # Trombay, mangroves, industrial — 15% of East crimes
        "total_crimes": round(11576 * 0.15),
        "severity": 0.35,
    },
    "South": {
        "total_crimes": 9590,
        "severity": 0.42,
    },
}


def get_region(lat: float, lng: float) -> str:
    # South — Colaba, Fort, Marine Lines, Worli, Mahim
    if lat < 19.020 and lng < 72.870:
        return "South"

    # East — split by longitude
    if lat >= 19.020 and lng >= 72.900:
        return "East_dense" if lng < 72.940 else "East_sparse"

    # Central — Sion, Dharavi, Kurla, inner belt
    if 19.020 <= lat < 19.110 and 72.840 <= lng < 72.910:
        return "Central"

    # North — Andheri east, Goregaon, Malad, Kandivali, Borivali
    if lat >= 19.110 and lng >= 72.850:
        return "North"

    # West — Bandra, Santacruz, Vile Parle, Andheri west, Juhu
    if lat >= 19.020 and lng < 72.900:
        return "West"

    return "Central"


def crime_only_score(crime_count: int, crime_severity: float) -> tuple:
    """Reference base_score using updated weights (crime 55%)."""
    crime_count_norm = min(crime_count / 10.0, 1.0)
    crime_score = (crime_count_norm * 0.6) + (crime_severity * 0.4)

    total = (
        crime_score * 55
        + 0.5 * 12   # neutral infra
        + 0.5 * 25   # neutral time
        + 0.5 * 5    # neutral weather
        + 0.3 * 3    # neutral context
    )
    total = round(min(max(total, 0), 100))

    if total <= 30:
        zone = "GREEN"
    elif total <= 55:
        zone = "YELLOW"
    elif total <= 75:
        zone = "ORANGE"
    else:
        zone = "RED"

    return total, zone


def main():
    input_file  = "hex_scores_enriched.json"
    backup_file = f"hex_scores_enriched_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    print(f"Loading {input_file}...")
    with open(input_file, "r") as f:
        hexes = json.load(f)
    print(f"Loaded {len(hexes):,} hex cells.")

    # Step 1: classify + count
    print("\nStep 1: Classifying hex cells into regions...")
    region_assignments = {}
    region_counts      = {r: 0 for r in REGION_CRIME_DATA}

    for cell in hexes:
        region = get_region(cell["lat"], cell["lng"])
        region_assignments[cell["hex_id"]] = region
        region_counts[region] += 1

    print("Hex cells per region:")
    for region, count in sorted(region_counts.items()):
        crimes  = REGION_CRIME_DATA[region]["total_crimes"]
        per_hex = round(crimes / max(count, 1))
        print(f"  {region:14s}: {count:,} hexes | {crimes:,} crimes | ~{per_hex} per hex")

    # Step 2: backup
    print(f"\nStep 2: Backup → {backup_file}")
    shutil.copy(input_file, backup_file)

    # Step 3: assign crime data
    print("\nStep 3: Rebuilding crime data per hex...")
    for i, cell in enumerate(hexes):
        region = region_assignments[cell["hex_id"]]
        data   = REGION_CRIME_DATA[region]
        count  = region_counts[region]

        cell["crime_count"]    = max(round(data["total_crimes"] / count), 1)
        cell["crime_severity"] = round(data["severity"], 3)
        cell["region"]         = region

        if (i + 1) % 2000 == 0:
            print(f"  {i+1:,} / {len(hexes):,}")

    print(f"  Done. {len(hexes):,} cells updated.")

    # Step 4: recalculate base_score + zone
    print("\nStep 4: Recalculating base_score and zone...")
    for cell in hexes:
        score, zone    = crime_only_score(cell["crime_count"], cell["crime_severity"])
        cell["base_score"] = score
        cell["zone"]       = zone

    # Step 5: write
    print(f"\nStep 5: Writing to {input_file}...")
    with open(input_file, "w") as f:
        json.dump(hexes, f, indent=2)

    # Summary
    zone_counts = {"GREEN": 0, "YELLOW": 0, "ORANGE": 0, "RED": 0}
    for cell in hexes:
        zone_counts[cell.get("zone", "GREEN")] += 1

    print("\n── Zone distribution ──")
    for zone in ["GREEN", "YELLOW", "ORANGE", "RED"]:
        c   = zone_counts[zone]
        pct = c / len(hexes) * 100
        print(f"  {zone:8s}: {c:,} hexes ({pct:.1f}%)")

    print(f"\nBackup: {backup_file}")
    print("Done. Restart main.py.")


if __name__ == "__main__":
    main()