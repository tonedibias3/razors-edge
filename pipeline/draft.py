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
    pool = []
    for pid in keep:
        p = roster[pid]
        pool.append([pid, p["name"], p["pos"], p["team"], conf.get(p["team"], ""), p["cls"], int(p["ht"]) if p["ht"] else None, int(p["wt"]) if p["wt"] else None, statline(stats[pid])])
    pool.sort(key=lambda r: (r[1].lower(), r[3]))
    return {"ok": True, "season": season, "built": int(time.time()), "pool": pool}


def load_cached(season):
    try:
        c = json.load(open(CACHE))
        if c.get("ok") and c.get("season") == season and time.time() - c.get("built", 0) < FRESH_SECONDS and c.get("pool"):
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
