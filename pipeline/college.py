"""College football (FBS) schedule, scores, betting lines and AP rankings from CollegeFootballData.com.
Adds a "college" section to work/data.json. It never stops the build: with no key, or if the site is down,
the section just says why and the page leaves College out."""
import json, os, re, statistics, sys, time, urllib.parse, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(__file__))
from config import WORK

BASES = ["https://apinext.collegefootballdata.com", "https://api.collegefootballdata.com"]
KEY = os.environ.get("CFBD_API_KEY", "").strip()
YEARS_BACK = 13  # this season plus 13 earlier ones (lines exist from 2013) for head-to-head; trends and "similar games" use the last five seasons
ET = ZoneInfo("America/New_York")
CACHE = os.environ.get("CFB_CACHE") or os.path.join(WORK, "cfb_cache")


class ApiError(Exception):
    pass


def get(path, params=None):
    last = None
    for base in BASES:
        url = base + path + ("?" + urllib.parse.urlencode(params) if params else "")
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"Authorization": "Bearer " + KEY, "Accept": "application/json", "User-Agent": "razors-edge"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    raise ApiError(f"CollegeFootballData rejected the key (HTTP {e.code}). Check the CFBD_API_KEY secret.")
                if e.code == 429:
                    time.sleep(10 * (attempt + 1)); last = e; continue
                last = e; break
            except Exception as e:
                last = e; time.sleep(3 * (attempt + 1))
    raise ApiError(f"could not reach CollegeFootballData ({last})")


def pick(d, *keys):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def num(v):
    try:
        return None if v is None else float(v)
    except Exception:
        return None


def half(v):
    return None if v is None else round(v * 2) / 2


def home_spread(line, home, away):
    """Spread in the NFL file's convention: positive means the HOME team is favored by that many."""
    fs = pick(line, "formattedSpread", "formatted_spread")
    if isinstance(fs, str):
        m = re.match(r"^(.*?)\s+([+-]?\d+(?:\.\d+)?)$", fs.strip())
        if m:
            team, val = m.group(1).strip(), float(m.group(2))
            if team == home:
                return -val
            if team == away:
                return val
        if re.search(r"\b(PK|pick)", fs, re.I):
            return 0.0
    sp = num(pick(line, "spread"))
    return None if sp is None else -sp


def et_parts(iso, tbd):
    if not iso:
        return "", ""
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(ET)
    except Exception:
        return str(iso)[:10], ""
    return dt.strftime("%Y-%m-%d"), ("" if tbd else dt.strftime("%H:%M"))


def build(season):
    teams_raw = get("/teams/fbs", {"year": season})
    teams, fbs = {}, set()
    for t in teams_raw:
        name = pick(t, "school")
        if not name:
            continue
        fbs.add(name)
        teams[name] = {"a": pick(t, "abbreviation") or name[:4].upper(), "c": [pick(t, "color") or "#555555", pick(t, "alternateColor", "alternate_color") or "#ffffff"], "conf": pick(t, "conference") or ""}
    if len(fbs) < 100:
        raise ApiError(f"expected about 130 FBS teams but got {len(fbs)}")
    rows = []
    os.makedirs(CACHE, exist_ok=True)
    for yr in range(season - YEARS_BACK, season + 1):
        # finished seasons never change, so they are fetched once and kept (the workflow caches this folder)
        cp = os.path.join(CACHE, f"lines_{yr}.json")
        if yr < season and os.path.exists(cp):
            try:
                old = json.load(open(cp))
                rows.extend(r for r in old if r[3] in fbs and r[4] in fbs)
                print(f"  {yr}: from cache", flush=True)
                continue
            except Exception:
                pass
        start = len(rows)
        games = get("/lines", {"year": yr, "seasonType": "regular"})
        used = 0
        for g in games:
            home, away = pick(g, "homeTeam", "home_team"), pick(g, "awayTeam", "away_team")
            if home not in fbs or away not in fbs:
                continue
            sp, ou = [], []
            for ln in g.get("lines") or []:
                s = home_spread(ln, home, away)
                if s is not None:
                    sp.append(s)
                o = num(pick(ln, "overUnder", "over_under"))
                if o is not None:
                    ou.append(o)
            if not sp:
                continue
            hp, ap = num(pick(g, "homeScore", "homePoints", "home_score", "home_points")), num(pick(g, "awayScore", "awayPoints", "away_score", "away_points"))
            done = hp is not None and ap is not None and (hp + ap) > 0
            d, t = et_parts(pick(g, "startDate", "start_date"), bool(pick(g, "startTimeTBD", "start_time_tbd")))
            rows.append([yr, int(g.get("week") or 0), d, away, home, (hp - ap) if done else None, half(statistics.median(sp)), half(statistics.median(ou)) if ou else None,
                         ap if done else None, hp if done else None, t, teams[away]["conf"], teams[home]["conf"]])
            used += 1
        print(f"  {yr}: {used} FBS games with lines", flush=True)
        if yr < season and used:
            json.dump(rows[start:], open(cp, "w"), separators=(",", ":"))
    rows.sort(key=lambda r: (r[0], r[1], r[2], r[10]))
    # AP poll by week (the poll listed for week N is the one in force for week N's games)
    ranks = {}
    try:
        for w in get("/rankings", {"year": season, "seasonType": "regular"}):
            polls = w.get("polls") or []
            poll = next((p for p in polls if "AP" in str(p.get("poll", ""))), polls[0] if polls else None)
            if poll:
                ranks[str(int(w.get("week") or 0))] = {pick(r, "school"): int(r.get("rank")) for r in poll.get("ranks", []) if pick(r, "school") and r.get("rank")}
    except ApiError as e:
        print("  rankings not loaded:", e)
    weeks = sorted({r[1] for r in rows if r[0] == season and r[5] is None})
    return {"ok": True, "season": season, "week": weeks[0] if weeks else None, "sched": rows, "teams": teams, "ranks": ranks}


if __name__ == "__main__":
    path = os.path.join(WORK, "data.json")
    data = json.load(open(path))
    if not KEY:
        data["college"] = {"ok": False, "reason": "No CFBD_API_KEY secret is set in the repository."}
        print("college: no CFBD_API_KEY, skipping")
    else:
        try:
            print("college: fetching from CollegeFootballData.com", flush=True)
            data["college"] = build(int(data["season"]))
            c = data["college"]
            print(f"college: {len(c['sched'])} games, {len(c['teams'])} teams, upcoming week {c['week']}, poll weeks {sorted(map(int, c['ranks']))}")
        except Exception as e:   # never block the NFL site
            msg = str(e)[:300]
            data["college"] = {"ok": False, "reason": msg}
            print("college: FAILED (site will build without it):", msg)
    json.dump(data, open(path, "w"), separators=(",", ":"))
