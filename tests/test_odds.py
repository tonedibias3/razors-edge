"""Checks for pipeline/odds.py using made-up API answers (no key or internet needed):  python3 tests/test_odds.py"""
import copy, json, os, sys, tempfile
os.environ["ODDS_CACHE"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))
import odds

ok = fail = 0
def check(name, cond):
    global ok, fail
    if cond: ok += 1; print("ok  ", name)
    else: fail += 1; print("FAIL", name)

def ev(home, away, when, bk):
    return {"home_team": home, "away_team": away, "commence_time": when, "bookmakers": bk}
def book(key, hp, tot):
    return {"key": key, "markets": [{"key": "spreads", "outcomes": [{"name": "H", "point": hp}]}, {"key": "totals", "outcomes": [{"name": "Over", "point": tot}, {"name": "Under", "point": tot}]}]}
def mk(home, away, when, key, hp, tot):
    b = book(key, hp, tot); b["markets"][0]["outcomes"] = [{"name": home, "point": hp}, {"name": away, "point": -hp}]
    return ev(home, away, when, [b])

base = {"season": 2026, "sched": [[2026, 5, "2026-10-08", "TB", "DAL", None, 8.5, 47.5, None, None, "20:15"],
                                  [2026, 5, "2026-10-11", "PHI", "JAX", None, 7.0, 42.5, None, None, "09:30"],
                                  [2026, 4, "2026-10-01", "PHI", "JAX", 3.0, 7.0, 42.5, 20.0, 23.0, "20:15"]],
        "college": {"ok": True, "season": 2026, "teams": {"Miami": {}, "Miami (OH)": {}, "Texas A&M": {}, "Alabama": {}, "Hawai'i": {}},
                    "sched": [[2026, 6, "2026-10-10", "Alabama", "Texas A&M", None, 3.0, 55.5, None, None, "15:30", "SEC", "SEC"],
                              [2026, 6, "2026-10-10", "Miami (OH)", "Miami", None, 20.0, 50.0, None, None, "12:00", "MAC", "ACC"]]}}
def api_nfl(sport):
    if sport == "americanfootball_nfl":
        return [mk("Dallas Cowboys", "Tampa Bay Buccaneers", "2026-10-09T00:15:00Z", "bovada", -7.5, 49.0),
                mk("Jacksonville Jaguars", "Philadelphia Eagles", "2026-10-11T13:30:00Z", "draftkings", -6.5, 43.0)], "480"
    return [mk("Texas A&M Aggies", "Alabama Crimson Tide", "2026-10-10T19:30:00Z", "bovada", 2.5, 56.5),
            mk("Miami Hurricanes", "Miami (OH) RedHawks", "2026-10-10T16:00:00Z", "fanduel", -21.5, 51.0)], "476"

d = copy.deepcopy(base)
odds.run(d, now=1_000_000, fetch=api_nfl, key="x")
dal = d["sched"][0]; jax = d["sched"][1]
check("NFL home spread flipped into our convention (DAL -7.5 -> 7.5)", dal[6] == 7.5 and dal[7] == 49.0)
check("falls back to the next book when Bovada is missing", jax[6] == 6.5 and jax[7] == 43.0)
check("played game is left alone", d["sched"][2][6] == 7.0)
c = d["college"]["sched"]
check("college Texas A&M home +2.5 matched", c[0][6] == -2.5 and c[0][7] == 56.5)
check("Miami (OH) is not confused with Miami", c[1][6] == 21.5 and c[1][7] == 51.0)
o = d["odds"]
check("odds section says updated and has credits", o["ok"] and o["credits"] == "476" and "nfl" in o["updated"] and "cfb" in o["updated"])
check("books counted by name", o["books"]["nfl"].get("Bovada") == 1 and o["books"]["nfl"].get("DraftKings") == 1)
check("history starts with one entry per game", all(len(v) == 1 for v in o["moves"]["nfl"].values()) and len(o["moves"]["nfl"]) == 2)

# second run later, line moved
def api_moved(sport):
    r, c = api_nfl(sport)
    if sport == "americanfootball_nfl": r[0] = mk("Dallas Cowboys", "Tampa Bay Buccaneers", "2026-10-09T00:15:00Z", "bovada", -6.5, 48.5)
    return r, c
d2 = copy.deepcopy(base)
odds.run(d2, now=1_000_000 + 4 * 3600, fetch=api_moved, key="x")
h = d2["odds"]["moves"]["nfl"]["2026|5|TB|DAL"]
check("movement is kept: opened 7.5, now 6.5", len(h) == 2 and h[0][1] == 7.5 and h[1][1] == 6.5 and d2["sched"][0][6] == 6.5)

# too soon: no fetch, saved lines reused
calls = []
def boom(sport): calls.append(sport); raise AssertionError("should not call the API")
d3 = copy.deepcopy(base)
odds.run(d3, now=1_000_000 + 4 * 3600 + 600, fetch=boom, key="x")
check("a run within 3 hours spends no credits and reuses saved lines", not calls and d3["sched"][0][6] == 6.5)

# failure keeps old lines
def down(sport): raise RuntimeError("service down")
d4 = copy.deepcopy(base)
odds.run(d4, now=1_000_000 + 20 * 3600, fetch=down, key="x")
check("when the service is down the last saved lines still apply", d4["sched"][0][6] == 6.5 and d4["odds"].get("error"))

# no key
d5 = copy.deepcopy(base)
odds.run(d5, key="")
check("no key: page keeps schedule lines", d5["sched"][0][6] == 8.5 and d5["odds"]["ok"] is False)

# old games pruned
state = {"history": {"nfl": {"k": [[1, 1, 1]]}}, "latest": {"nfl": {"k": [1, 1, 1]}}}
odds.prune(state, 1 + 30 * 86400)
check("old history is pruned", state["history"]["nfl"] == {})
print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
