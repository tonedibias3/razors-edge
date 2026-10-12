"""NFL injury report from ESPN's public feed (no key, no signup). Adds an "injuries" section to work/data.json:
{team abbr: [[name, position, status, note], ...]}, worst first. Never stops the build: if ESPN is down the page just shows no injuries."""
import json, os, sys, time, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(__file__))
from config import WORK
from odds import NFL_NAMES

URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
RANK = {"out": 0, "injured reserve": 0, "ir": 0, "doubtful": 1, "questionable": 2, "day-to-day": 3}
SHORT = {"out": "Out", "injured reserve": "IR", "ir": "IR", "doubtful": "Doubtful", "questionable": "Questionable", "day-to-day": "Day-to-day"}
POS_RANK = {"QB": 0, "RB": 1, "WR": 2, "TE": 3, "OT": 4, "T": 4, "G": 5, "C": 5, "OL": 5, "DE": 6, "DT": 6, "LB": 7, "CB": 8, "S": 8, "K": 9}


def fetch():
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "razors-edge"}), timeout=40) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e; time.sleep(2 * (attempt + 1))
    raise RuntimeError(str(last))


def parse(j):
    out = {}
    for t in j.get("injuries", []):
        abbr = NFL_NAMES.get(t.get("displayName", ""))
        if not abbr:
            continue
        rows = []
        for i in t.get("injuries", []):
            a = i.get("athlete") or {}
            st = str(i.get("status") or "").strip()
            key = st.lower()
            if key not in RANK or not a.get("displayName"):
                continue
            pos = ((a.get("position") or {}).get("abbreviation")) or ""
            d = i.get("details") or {}
            note = d.get("type") or (i.get("type") or {}).get("description") or ""
            rows.append([a["displayName"], pos, SHORT[key], str(note)[:40]])
        rows.sort(key=lambda r: (RANK[r[2].lower()] if r[2].lower() in RANK else 3, POS_RANK.get(r[1], 10), r[0]))
        if rows:
            out[abbr] = rows
    return out


def main():
    path = os.path.join(WORK, "data.json")
    data = json.load(open(path, encoding="utf-8"))
    inj = parse(fetch())
    data["injuries"] = {"ok": bool(inj), "at": datetime.now(ZoneInfo("America/New_York")).strftime("%a %b %d %-I:%M %p ET"), "nfl": inj}
    json.dump(data, open(path, "w", encoding="utf-8"))
    print(f"injuries: {sum(len(v) for v in inj.values())} players on {len(inj)} teams")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never stop the build over injuries
        print("injuries: skipped,", e)
