"""College team yardage and points, game by game, from CollegeFootballData.com (/games/teams).
Adds "cstats" to work/data.json: one row per team per game against another FBS team:
[week, team, opponent, pass yds (net), rush yds, points, opp pass yds, opp rush yds, opp points].
Never stops the build: with no key, or if the site is down, the section just says why and the page leaves college stats out.
Finished weeks are kept in the cache folder, so a normal run only asks for the last couple of weeks."""
import json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from config import WORK
import college
from college import ApiError, get, pick, num

MAX_WEEK = 16


def fnum(v):
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return None


def parse_week(games, fbs, week):
    """Rows for one week from the /games/teams answer. Games with an FCS opponent or missing numbers are skipped."""
    out = []
    for g in games or []:
        ts = g.get("teams") or []
        if len(ts) != 2:
            continue
        side = []
        for t in ts:
            st = {str(s.get("category")): fnum(s.get("stat")) for s in (t.get("stats") or [])}
            side.append((pick(t, "school", "team"), num(pick(t, "points")), st.get("netPassingYards"), st.get("rushingYards")))
        (a, ap, apass, arush), (b, bp, bpass, brush) = side
        if a not in fbs or b not in fbs or None in (ap, apass, arush, bp, bpass, brush):
            continue
        out.append([week, a, b, int(apass), int(arush), int(ap), int(bpass), int(brush), int(bp)])
        out.append([week, b, a, int(bpass), int(brush), int(bp), int(apass), int(arush), int(ap)])
    return out


def build(season, fbs, current_week, fetch=get, cache_dir=None):
    rows, last = [], min(MAX_WEEK, current_week or MAX_WEEK)
    for w in range(1, last + 1):
        cp = os.path.join(cache_dir, f"cstats_{season}_w{w}.json") if cache_dir else None
        if cp and w <= last - 2 and os.path.exists(cp):
            try:
                rows.extend(json.load(open(cp)))
                continue
            except Exception:
                pass
        wr = parse_week(fetch("/games/teams", {"year": season, "week": w, "seasonType": "regular"}), fbs, w)
        rows.extend(wr)
        if cp and wr:
            os.makedirs(cache_dir, exist_ok=True)
            json.dump(wr, open(cp, "w"), separators=(",", ":"))
        print(f"  week {w}: {len(wr) // 2} games", flush=True)
    if len({r[1] for r in rows}) < 40:
        raise ApiError(f"expected stats for many teams but got {len({r[1] for r in rows})}")
    return {"ok": True, "season": season, "rows": rows}


if __name__ == "__main__":
    path = os.path.join(WORK, "data.json")
    data = json.load(open(path))
    col = data.get("college") or {}
    if not college.KEY:
        data["cstats"] = {"ok": False, "reason": "No CFBD_API_KEY secret is set in the repository."}
        print("cstats: no CFBD_API_KEY, skipping")
    elif not col.get("ok"):
        data["cstats"] = {"ok": False, "reason": "College data is not available."}
        print("cstats: college data missing, skipping")
    else:
        try:
            print("cstats: fetching college team stats", flush=True)
            data["cstats"] = build(int(col["season"]), set(col["teams"]), col.get("week"), cache_dir=college.CACHE)
            print(f"cstats: {len(data['cstats']['rows']) // 2} team-games")
        except Exception as e:  # never block the rest of the site
            data["cstats"] = {"ok": False, "reason": str(e)[:300]}
            print("cstats: FAILED (site will build without college stats):", str(e)[:300])
    json.dump(data, open(path, "w"), separators=(",", ":"))
