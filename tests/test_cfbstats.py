"""Checks the college team-stats code with made-up CollegeFootballData answers (no key or internet needed)."""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
os.environ.setdefault("CFB_CACHE", "/tmp/claude-0/test_cfb_cache")
import cfbstats

ok = True


def t(name, cond):
    global ok
    print("ok  " if cond else "FAIL", name)
    ok = ok and bool(cond)


def team(school, pts, p, r):
    return {"school": school, "points": pts, "stats": [{"category": "netPassingYards", "stat": str(p)}, {"category": "rushingYards", "stat": str(r)}, {"category": "totalYards", "stat": str(p + r)}]}


fbs = {f"T{i}" for i in range(60)}
calls = []


def fake(path, params=None):
    calls.append(params["week"])
    w = params["week"]
    g = [{"id": 1, "teams": [team("T1", 30, 250, 150), team("T2", 20, 180, 90)]}, {"id": 2, "teams": [team("T3", 10, 100, 50), team("FCS State", 40, 300, 200)]}]
    g += [{"id": 10 + i, "teams": [team(f"T{i}", 21, 200, 100), team(f"T{i + 1}", 14, 150, 80)]} for i in range(4, 58, 2)]
    return g


with tempfile.TemporaryDirectory() as d:
    r = cfbstats.build(2026, fbs, 3, fake, d)
    rows = r["rows"]
    t("builds ok", r["ok"] and r["season"] == 2026)
    t("every game gives a row for each team", len([x for x in rows if x[0] == 1 and x[1] == "T1"]) == 1 and len([x for x in rows if x[0] == 1 and x[1] == "T2"]) == 1)
    t("FCS opponent game is skipped", not any(x[1] == "FCS State" or x[2] == "FCS State" for x in rows))
    t("row has offense then opponent numbers", [x for x in rows if x[0] == 1 and x[1] == "T1"][0] == [1, "T1", "T2", 250, 150, 30, 180, 90, 20])
    calls.clear()
    cfbstats.build(2026, fbs, 4, fake, d)
    t("finished weeks come from the cache, recent ones are fetched again", calls == [3, 4])
try:
    cfbstats.build(2026, fbs, 2, lambda p, q=None: [], None)
    t("empty answer raises", False)
except cfbstats.ApiError:
    t("empty answer raises", True)
print("ALL PASSED" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
