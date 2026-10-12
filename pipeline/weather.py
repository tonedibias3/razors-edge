"""Kickoff weather for upcoming NFL games from Open-Meteo (open-meteo.com): free, no key, no signup.
Adds a "weather" section to work/data.json, keyed "season|week|away|home". It never stops the build:
if the service is down or a game is too far out (forecasts reach about 16 days), that game just has no weather."""
import json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(__file__))
from config import WORK

ET = ZoneInfo("America/New_York")
# team: (lat, lon, roof)  roof: "open", "dome" (always indoors) or "retract" (roof may be open or closed)
NFL_PARKS = {
    "ARI": (33.5276, -112.2626, "retract"), "ATL": (33.7554, -84.4009, "dome"), "BAL": (39.2780, -76.6227, "open"),
    "BUF": (42.7738, -78.7870, "open"), "CAR": (35.2258, -80.8528, "open"), "CHI": (41.8623, -87.6167, "open"),
    "CIN": (39.0955, -84.5161, "open"), "CLE": (41.5061, -81.6995, "open"), "DAL": (32.7473, -97.0945, "retract"),
    "DEN": (39.7439, -105.0201, "open"), "DET": (42.3400, -83.0456, "dome"), "GB": (44.5013, -88.0622, "open"),
    "HOU": (29.6847, -95.4107, "retract"), "IND": (39.7601, -86.1639, "retract"), "JAX": (30.3239, -81.6373, "open"),
    "KC": (39.0489, -94.4839, "open"), "LV": (36.0909, -115.1833, "dome"), "LAC": (33.9535, -118.3392, "dome"),
    "LA": (33.9535, -118.3392, "dome"), "MIA": (25.9580, -80.2389, "open"), "MIN": (44.9735, -93.2575, "dome"),
    "NE": (42.0909, -71.2643, "open"), "NO": (29.9511, -90.0812, "dome"), "NYG": (40.8135, -74.0745, "open"),
    "NYJ": (40.8135, -74.0745, "open"), "PHI": (39.9008, -75.1675, "open"), "PIT": (40.4468, -80.0158, "open"),
    "SEA": (47.5952, -122.3316, "open"), "SF": (37.4030, -121.9700, "open"), "TB": (27.9759, -82.5033, "open"),
    "TEN": (36.1665, -86.7713, "open"), "WAS": (38.9076, -76.8645, "open"),
}
URL = "https://api.open-meteo.com/v1/forecast"


def fetch(lat, lon):
    q = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 16,
        "temperature_unit": "fahrenheit", "wind_speed_unit": "mph", "precipitation_unit": "inch",
        "hourly": "temperature_2m,wind_speed_10m,wind_gusts_10m,precipitation_probability,precipitation,weather_code"})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(URL + "?" + q, headers={"User-Agent": "razors-edge"}), timeout=40) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e; time.sleep(2 * (attempt + 1))
    raise RuntimeError(str(last))


def game_weather(resp, date, hhmm, roof):
    """Weather over the three hours starting at kickoff (kickoff times in the schedule are Eastern)."""
    h = resp.get("hourly") or {}
    times = h.get("time") or []
    tz = ZoneInfo(resp.get("timezone") or "America/New_York")
    try:
        ko = datetime.fromisoformat(f"{date}T{hhmm or '13:00'}").replace(tzinfo=ET).astimezone(tz)
    except Exception:
        return None
    idx = []
    for k in range(3):
        stamp = (ko + timedelta(hours=k)).strftime("%Y-%m-%dT%H:00")
        if stamp in times:
            idx.append(times.index(stamp))
    if not idx:
        return None
    pick = lambda name: [h[name][i] for i in idx if h.get(name) and h[name][i] is not None]
    t, w, g, pp, pr, code = pick("temperature_2m"), pick("wind_speed_10m"), pick("wind_gusts_10m"), pick("precipitation_probability"), pick("precipitation"), pick("weather_code")
    if not t:
        return None
    return {"roof": roof, "temp": round(sum(t) / len(t)), "wind": round(max(w)) if w else None, "gust": round(max(g)) if g else None,
            "pop": round(max(pp)) if pp else None, "rain": round(sum(pr), 2) if pr else None, "code": max(code) if code else None}


def main():
    path = os.path.join(WORK, "data.json")
    data = json.load(open(path, encoding="utf-8"))
    today = datetime.now(ET).strftime("%Y-%m-%d"); horizon = (datetime.now(ET) + timedelta(days=15)).strftime("%Y-%m-%d")
    games = [r for r in data.get("sched", []) if r[5] is None and today <= r[2] <= horizon and r[4] in NFL_PARKS]
    out, cache = {}, {}
    for r in games:
        season, week, date, away, home, hhmm = r[0], r[1], r[2], r[3], r[4], r[10] if len(r) > 10 else None
        lat, lon, roof = NFL_PARKS[home]
        try:
            if home not in cache:
                cache[home] = fetch(lat, lon)
            w = game_weather(cache[home], date, hhmm, roof)
        except Exception as e:
            print(f"weather: {home} skipped ({e})"); continue
        if w:
            out[f"{season}|{week}|{away}|{home}"] = w
    data["weather"] = {"ok": bool(out), "at": datetime.now(ET).strftime("%Y-%m-%d %H:%M ET"), "nfl": out}
    json.dump(data, open(path, "w", encoding="utf-8"))
    print(f"weather: {len(out)} games")


if __name__ == "__main__":
  try:
    main()
  except Exception as e:  # never stop the build over weather
    print("weather: skipped,", e)
