# weather_layer.py
# Fetches current weather for a lat/lng and returns a normalized score 0.0–1.0
# This score plugs directly into score_engine.py as weather_score

import requests

OWM_API_KEY = "621e46957d876272d713c10378889fe9"  # ← paste your key here
OWM_URL = "https://api.openweathermap.org/data/2.5/weather"

# ----------------------------
# Weather condition weights
# OWM uses numeric condition codes:
# https://openweathermap.org/weather-conditions
# ----------------------------
# We group them into risk buckets 0.0–1.0
CONDITION_SCORE = {
    # Clear / good conditions
    800: 0.0,   # clear sky
    801: 0.1,   # few clouds
    802: 0.1,   # scattered clouds
    803: 0.2,   # broken clouds
    804: 0.2,   # overcast clouds

    # Drizzle — minor inconvenience
    300: 0.3, 301: 0.3, 302: 0.4,
    310: 0.3, 311: 0.3, 312: 0.4,
    313: 0.4, 314: 0.4, 321: 0.3,

    # Rain — moderate risk (visibility, flooding)
    500: 0.4,   # light rain
    501: 0.5,   # moderate rain
    502: 0.7,   # heavy rain
    503: 0.8,   # very heavy rain
    504: 0.9,   # extreme rain
    511: 0.6,   # freezing rain
    520: 0.4,   # light shower
    521: 0.5,   # shower rain
    522: 0.7,   # heavy shower
    531: 0.6,   # ragged shower

    # Thunderstorm — high risk
    200: 0.7, 201: 0.8, 202: 0.9,
    210: 0.6, 211: 0.7, 212: 0.9,
    221: 0.8, 230: 0.7, 231: 0.8,
    232: 0.9,

    # Snow — low Mumbai relevance but included
    600: 0.4, 601: 0.5, 602: 0.7,
    611: 0.5, 612: 0.5, 613: 0.6,
    615: 0.4, 616: 0.5, 620: 0.4,
    621: 0.6, 622: 0.8,

    # Atmosphere (fog, haze, smoke, dust)
    701: 0.4,   # mist
    711: 0.6,   # smoke
    721: 0.3,   # haze
    731: 0.5,   # dust whirls
    741: 0.5,   # fog
    751: 0.5,   # sand
    761: 0.5,   # dust
    762: 0.7,   # volcanic ash
    771: 0.8,   # squalls
    781: 1.0,   # tornado
}


def get_weather_score(lat: float, lng: float) -> dict:
    """
    Fetches live weather for a lat/lng.
    Returns a normalized score 0.0–1.0 + metadata for reason cards.

    On API failure → returns neutral score 0.5 so scoring still works.
    """

    try:
        response = requests.get(
            OWM_URL,
            params={
                "lat": lat,
                "lon": lng,
                "appid": OWM_API_KEY,
                "units": "metric"      # celsius, m/s wind
            },
            timeout=5                  # don't hang if OWM is slow
        )

        response.raise_for_status()
        data = response.json()

        # --- Extract what we need ---
        condition_id   = data["weather"][0]["id"]
        condition_desc = data["weather"][0]["description"]
        temp_c         = data["main"]["temp"]
        humidity       = data["main"]["humidity"]
        wind_mps       = data["wind"]["speed"]
        visibility_m   = data.get("visibility", 10000)  # defaults to clear if missing

        # --- Base score from condition code ---
        base = CONDITION_SCORE.get(condition_id, 0.3)  # unknown code → mild caution

        # --- Modifier: extreme heat (Mumbai-specific) ---
        # Above 38°C adds risk (heat exhaustion, crowd volatility)
        heat_penalty = 0.0
        if temp_c >= 42:
            heat_penalty = 0.15
        elif temp_c >= 38:
            heat_penalty = 0.08

        # --- Modifier: low visibility ---
        # Below 1km adds risk (accidents, disorientation)
        visibility_penalty = 0.0
        if visibility_m < 500:
            visibility_penalty = 0.15
        elif visibility_m < 1000:
            visibility_penalty = 0.08

        # --- Modifier: high wind ---
        # Above 15 m/s (54 km/h) is dangerous
        wind_penalty = 0.0
        if wind_mps >= 20:
            wind_penalty = 0.15
        elif wind_mps >= 15:
            wind_penalty = 0.08

        # --- Final score (capped at 1.0) ---
        final = min(1.0, base + heat_penalty + visibility_penalty + wind_penalty)
        # test only — force a bad weather score
    
        return {
            "weather_score": round(final, 3),
            "condition": condition_desc,
            "condition_id": condition_id,
            "temp_c": temp_c,
            "humidity": humidity,
            "wind_mps": wind_mps,
            "visibility_m": visibility_m,
            "source": "live"
        }

    except requests.exceptions.Timeout:
        print(f"[weather_layer] Timeout for ({lat}, {lng}) — using neutral score")
        return _neutral("timeout")

    except requests.exceptions.RequestException as e:
        print(f"[weather_layer] API error: {e} — using neutral score")
        return _neutral("api_error")


def _neutral(reason: str) -> dict:
    """Fallback when API fails — neutral score so scoring pipeline doesn't break."""
    return {
        "weather_score": 0.5,
        "condition": "unknown",
        "condition_id": None,
        "temp_c": None,
        "humidity": None,
        "wind_mps": None,
        "visibility_m": None,
        "source": reason
    }


# --- Quick test ---
if __name__ == "__main__":
    test_locations = [
        {"name": "CST Mumbai",    "lat": 19.0760, "lng": 72.8777},
        {"name": "Bandra",        "lat": 19.0596, "lng": 72.8295},
        {"name": "Andheri East",  "lat": 19.1136, "lng": 72.8697},
    ]

    for loc in test_locations:
        result = get_weather_score(loc["lat"], loc["lng"])
        print(f"\n{loc['name']}")
        print(f"  Condition : {result['condition']}")
        print(f"  Temp      : {result['temp_c']}°C")
        print(f"  Wind      : {result['wind_mps']} m/s")
        print(f"  Visibility: {result['visibility_m']} m")
        print(f"  Score     : {result['weather_score']} → feeds into score_engine as weather_score")