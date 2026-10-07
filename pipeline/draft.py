"""NFL draft prospect pool from CollegeFootballData.com: juniors and seniors with the best production this season.
Adds a "draft" section to work/data.json. It never stops the build: with no key, or if the site is down, the section
just says why. The pool is a search list for YOUR board (it is not a ranking); you build the order yourself on the page.
The result is kept for about a day in the cache folder so twice-daily runs don't spend extra API calls."""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(__file__))
from config import WORK
import college
from college import ApiError, get, pick, num

CACHE = os.path.join(college.CACHE, "draft_pool.json")
FRESH_SECONDS = 20 * 3600
MIN_CLASS = 3  # class year 3 = junior, 4 = senior, 5 = fifth year
VERSION = 2    # bump when the pool's shape changes so an older cached copy is not reused
P4 = {"SEC", "Big Ten", "Big 12", "ACC"}   # linemen have no stats, so they are added by roster for these conferences (and Notre Dame)
OL = {"OL", "OT", "OG", "C", "IOL"}
GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "APB": "RB", "WR": "WR", "TE": "TE", "DL": "DL", "DT": "DL", "NT": "DL", "DE": "DL", "EDGE": "DL", "LB": "LB", "ILB": "LB", "OLB": "LB", "DB": "DB", "CB": "DB", "S": "DB", "FS": "DB", "SS": "DB"}

# (stat category, the stat used to rank within it, how many to keep)
CATS = [("passing", "YDS", 120), ("rushing", "YDS", 200), ("receiving", "YDS", 320), ("defensive", "TOT", 300), ("defensive", "SACKS", 150), ("defensive", "TFL", 100), ("interceptions", "INT", 60)]


def fnum(v):
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return None


def fmt(v):
    return "" if v is None else (str(int(v)) if float(v).is_integer() else str(round(v, 1)))


def statline(s):
    """One short line of this season's numbers from {category: {STAT: value}}."""
    g = lambda c, k: s.get(c, {}).get(k)
    parts = []
    if g("passing", "YDS") is not None:
        parts.append(f"{fmt(g('passing', 'YDS'))} pass yds, {fmt(g('passing', 'TD'))} TD, {fmt(g('passing', 'INT'))} INT")
    if g("rushing", "YDS") is not None:
        parts.append(f"{fmt(g('rushing', 'CAR'))} car, {fmt(g('rushing', 'YDS'))} yds, {fmt(g('rushing', 'TD'))} TD")
    if g("receiving", "YDS") is not None:
        parts.append(f"{fmt(g('receiving', 'REC'))} rec, {fmt(g('receiving', 'YDS'))} yds, {fmt(g('receiving', 'TD'))} TD")
    if g("defensive", "TOT") is not None:
        d = [f"{fmt(g('defensive', 'TOT'))} tkl"]
        if g("defensive", "SACKS"):
            d.append(f"{fmt(g('defensive', 'SACKS'))} sacks")
        if g("defensive", "TFL"):
            d.append(f"{fmt(g('defensive', 'TFL'))} TFL")
        if g("interceptions", "INT"):
            d.append(f"{fmt(g('interceptions', 'INT'))} INT")
        parts.append(", ".join(d))
    elif g("interceptions", "INT"):
        parts.append(f"{fmt(g('interceptions', 'INT'))} INT")
    return " | ".join(parts)


def production(pos, s):
    """One number to sort a position by, using this season's main stat: passing yards for QBs, rushing yards for RBs, receiving yards
    for WR/TE, sacks for linemen and edge players (tackles for loss break ties), tackles for linebackers and defensive backs. Not a grade."""
    g = GROUP.get(str(pos).upper())
    d = lambda c, k: s.get(c, {}).get(k) or 0
    if g == "QB": return d("passing", "YDS")
    if g == "RB": return d("rushing", "YDS")
    if g in ("WR", "TE"): return d("receiving", "YDS")
    if g == "DL": return d("defensive", "SACKS") + d("defensive", "TFL") / 100
    if g in ("LB", "DB"): return d("defensive", "TOT")
    return 0


def build(season, fetch=get):
    roster = {}
    for p in fetch("/roster", {"year": season}):
        pid = pick(p, "id", "playerId")
        yr = num(pick(p, "year"))
        if pid is None or yr is None or yr < MIN_CLASS:
            continue
        name = (str(pick(p, "firstName", "first_name") or "") + " " + str(pick(p, "lastName", "last_name") or "")).strip()
        if not name:
            continue
        roster[str(pid)] = {"name": name, "pos": pick(p, "position") or "", "team": pick(p, "team") or "", "cls": int(yr), "ht": num(pick(p, "height")), "wt": num(pick(p, "weight"))}
    if len(roster) < 500:
        raise ApiError(f"expected a few thousand juniors and seniors but got {len(roster)}")
    stats = {}
    cats = sorted({c for c, _, _ in CATS} | {"interceptions"})
    for cat in cats:
        for r in fetch("/stats/player/season", {"year": season, "category": cat, "seasonType": "regular"}):
            pid, st, v = str(pick(r, "playerId", "player_id")), str(pick(r, "statType", "stat_type") or "").upper(), fnum(pick(r, "stat"))
            if pid in roster and v is not None:
                stats.setdefault(pid, {}).setdefault(cat, {})[st] = v
    keep = set()
    for cat, key, n in CATS:
        ranked = sorted((p for p in stats if key in stats[p].get(cat, {})), key=lambda p: -stats[p][cat][key])
        keep.update(ranked[:n])
    conf = {}
    try:
        conf = {t["school"]: t.get("conference") or "" for t in fetch("/teams/fbs", {"year": season}) if t.get("school")}
    except Exception:
        pass
    for pid, p in roster.items():   # linemen: no stats to rank them by, so take them by roster from the big conferences
        if pid not in keep and str(p["pos"]).upper() in OL and (conf.get(p["team"]) in P4 or p["team"] == "Notre Dame"):
            keep.add(pid)
    pool = []
    for pid in keep:
        p = roster[pid]
        pool.append([pid, p["name"], p["pos"], p["team"], conf.get(p["team"], ""), p["cls"], int(p["ht"]) if p["ht"] else None, int(p["wt"]) if p["wt"] else None, statline(stats.get(pid, {})), round(production(p["pos"], stats.get(pid, {})), 2)])
    pool.sort(key=lambda r: (r[1].lower(), r[3]))
    return {"ok": True, "v": VERSION, "season": season, "built": int(time.time()), "pool": pool}


def load_cached(season):
    try:
        c = json.load(open(CACHE))
        if c.get("ok") and c.get("v") == VERSION and c.get("season") == season and time.time() - c.get("built", 0) < FRESH_SECONDS and c.get("pool"):
            return c
    except Exception:
        pass
    return None


if __name__ == "__main__":
    path = os.path.join(WORK, "data.json")
    data = json.load(open(path))
    season = int((data.get("college") or {}).get("season") or data["season"])
    if not college.KEY:
        data["draft"] = {"ok": False, "reason": "No CFBD_API_KEY secret is set in the repository."}
        print("draft: no CFBD_API_KEY, skipping")
    else:
        try:
            c = load_cached(season)
            if c:
                print(f"draft: reusing the pool built {round((time.time() - c['built']) / 3600, 1)} hours ago ({len(c['pool'])} players)")
            else:
                print("draft: fetching rosters and stats from CollegeFootballData.com", flush=True)
                c = build(season)
                os.makedirs(os.path.dirname(CACHE), exist_ok=True)
                json.dump(c, open(CACHE, "w"), separators=(",", ":"))
                print(f"draft: {len(c['pool'])} prospects")
            data["draft"] = c
        except Exception as e:  # never block the rest of the site
            data["draft"] = {"ok": False, "reason": str(e)[:300]}
            print("draft: FAILED (site will build without the prospect pool):", str(e)[:300])
    json.dump(data, open(path, "w"), separators=(",", ":"))
