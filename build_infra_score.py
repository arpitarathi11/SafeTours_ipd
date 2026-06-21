"""
build_infra_scores.py — Phase 6a
=================================
One-time precompute script.

Reads  : hex_scores.json          (12,911 hex cells with lat/lng)
Writes : hex_scores_enriched.json (same records + infra_score field)

For each hex centroid:
  1. Query Overpass API for the nearest police station (amenity=police)
  2. Query Overpass API for the nearest hospital    (amenity=hospital)
  3. Compute infra_score from those two distances
  4. Write enriched record into output file

Scoring logic
-------------
  Distance bands (metres) → component score:
    0 – 500    → 0.1  (very close = very safe)
    501 – 1000 → 0.3
    1001 – 2000→ 0.5  (default when data missing)
    2001 – 3000→ 0.7
    > 3000     → 0.9  (far from emergency services = riskier)

  infra_score = mean(police_component, hospital_component)
  Clamped to [0.0, 1.0], rounded to 3 dp.

Worker config (default)
-----------------------
  WORKERS=3, DELAY=0.6s -> ~2.5 hrs for 12,911 cells.
  Stays under Overpass fair-use (~3 req/s across threads).
  Override via env vars:
    OVERPASS_WORKERS=1   (safe/slow, ~8 hrs)
    OVERPASS_WORKERS=5   (fast, needs your own Overpass instance)
    OVERPASS_DELAY=1.1   (conservative)

Resume / crash safety
----------------------
  Checks existing output file and skips already-enriched hex_ids.
  Safe to interrupt and re-run -- only unfinished cells are processed.

Usage
-----
  pip install requests
  python build_infra_scores.py
  python build_infra_scores.py --input hex_scores.json --output hex_scores_enriched.json
  python build_infra_scores.py --save-every 100

  Optional env vars:
    OVERPASS_URL=https://your-own-instance/api/interpreter
    OVERPASS_WORKERS=3
    OVERPASS_DELAY=0.6
"""

import argparse
import json
import math
import os
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import requests

# -- Config -------------------------------------------------------------------
OVERPASS_URL        = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
DELAY_BETWEEN_REQS  = float(os.getenv("OVERPASS_DELAY",   "0.6"))
WORKERS             = int(os.getenv("OVERPASS_WORKERS",   "3"))
SEARCH_RADIUS_M     = 5000
FALLBACK_RADIUS_M   = 10000
DEFAULT_INFRA_SCORE = 0.5   # used when BOTH queries fail (network/timeout)

# Distance -> risk component score
DISTANCE_BANDS = [
    (500,  0.1),
    (1000, 0.3),
    (2000, 0.5),
    (3000, 0.7),
]
FAR_SCORE = 0.9

# -- Helpers ------------------------------------------------------------------

def distance_to_score(metres):
    if metres is None:
        return DEFAULT_INFRA_SCORE
    for threshold, score in DISTANCE_BANDS:
        if metres <= threshold:
            return score
    return FAR_SCORE


def haversine_m(lat1, lng1, lat2, lng2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def overpass_nearest(lat, lng, amenity, radius):
    query = (
        "[out:json][timeout:10];\n"
        "(\n"
        f"  node[amenity={amenity}](around:{radius},{lat},{lng});\n"
        f"  way[amenity={amenity}](around:{radius},{lat},{lng});\n"
        ");\n"
        "out center 1;\n"
    )
    try:
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=15,
            headers={"User-Agent": "SafetyTourismApp/6a-infra-build"},
        )
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
        if not elements:
            return None
        el = elements[0]
        el_lat = el.get("lat") or el.get("center", {}).get("lat")
        el_lng = el.get("lon") or el.get("center", {}).get("lon")
        if el_lat is None or el_lng is None:
            return None
        return haversine_m(lat, lng, el_lat, el_lng)
    except requests.RequestException:
        return None


def query_with_fallback(lat, lng, amenity):
    dist = overpass_nearest(lat, lng, amenity, SEARCH_RADIUS_M)
    if dist is None:
        dist = overpass_nearest(lat, lng, amenity, FALLBACK_RADIUS_M)
    return dist


def compute_infra_score(lat, lng):
    police_dist   = query_with_fallback(lat, lng, "police")
    time.sleep(DELAY_BETWEEN_REQS)
    hospital_dist = query_with_fallback(lat, lng, "hospital")
    time.sleep(DELAY_BETWEEN_REQS)

    police_score   = distance_to_score(police_dist)
    hospital_score = distance_to_score(hospital_dist)
    infra_score    = round((police_score + hospital_score) / 2, 3)

    return {
        "infra_score":     infra_score,
        "police_dist_m":   round(police_dist)   if police_dist   is not None else None,
        "hospital_dist_m": round(hospital_dist) if hospital_dist is not None else None,
    }

# -- Persistence --------------------------------------------------------------

def load_existing(output_path):
    if not os.path.exists(output_path):
        return {}
    with open(output_path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return {}
    return {r["hex_id"]: r for r in data if "infra_score" in r}


def save_all(output_path, source, enriched_map):
    ordered = [enriched_map.get(r["hex_id"], r) for r in source]
    tmp = output_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ordered, f, indent=2)
    os.replace(tmp, output_path)

# -- Worker -------------------------------------------------------------------

def process_hex(record):
    try:
        infra = compute_infra_score(record["lat"], record["lng"])
        return {**record, **infra}
    except Exception as exc:
        print(f"  ERROR {record['hex_id']}: {exc}", file=sys.stderr)
        return {
            **record,
            "infra_score":     DEFAULT_INFRA_SCORE,
            "police_dist_m":   None,
            "hospital_dist_m": None,
        }

# -- Main ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Phase 6a: precompute infra scores")
    parser.add_argument("--input",      default="hex_scores.json")
    parser.add_argument("--output",     default="hex_scores_enriched.json")
    parser.add_argument("--save-every", type=int, default=50)
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        source = json.load(f)
    total = len(source)

    done         = load_existing(args.output)
    enriched_map = dict(done)
    todo         = [r for r in source if r["hex_id"] not in enriched_map]

    print(f"Loaded {total} hex cells from {args.input}")
    print(f"Workers: {WORKERS} | Delay: {DELAY_BETWEEN_REQS}s | ~{len(todo)*DELAY_BETWEEN_REQS*2/WORKERS/3600:.1f} hrs remaining")
    print(f"Resuming: {len(done)} done, {len(todo)} remaining\n")

    lock      = Lock()
    processed = 0
    errors    = 0
    start     = time.time()

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(process_hex, r): r for r in todo}
        for future in as_completed(futures):
            result = future.result()
            has_real_data = (
                result.get("police_dist_m") is not None
                or result.get("hospital_dist_m") is not None
            )

            with lock:
                enriched_map[result["hex_id"]] = result
                processed += 1
                if not has_real_data:
                    errors += 1

                if processed % args.save_every == 0 or processed == len(todo):
                    save_all(args.output, source, enriched_map)
                    total_done = len(enriched_map)
                    pct        = total_done / total * 100
                    elapsed    = time.time() - start
                    rate       = processed / elapsed if elapsed > 0 else 0
                    eta_s      = (len(todo) - processed) / rate if rate > 0 else 0
                    eta_m      = int(eta_s / 60)
                    print(
                        f"  [{pct:5.1f}%] {total_done}/{total} | "
                        f"this run: {processed} | fallbacks: {errors} | "
                        f"ETA: {eta_m} min"
                    )

    save_all(args.output, source, enriched_map)
    elapsed = time.time() - start
    print(f"\nDone in {elapsed/60:.1f} min.")
    print(f"Output : {args.output}")
    print(f"Total  : {total} | Processed this run: {processed} | Fallback (0.5): {errors}")


if __name__ == "__main__":
    main()