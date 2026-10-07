"""Checks the draft prospect pool code with made-up CollegeFootballData answers (no key or internet needed)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
os.environ.setdefault("CFB_CACHE", "/tmp/claude-0/test_cfb_cache")
import draft

ok = True


def t(name, cond):
    global ok
    print("ok  " if cond else "FAIL", name)
    ok = ok and bool(cond)


def fake(path, params=None):
    if path == "/roster":
        rows = [{"id": i, "firstName": "P", "lastName": str(i), "team": "State", "year": 1 + i % 4, "position": "WR", "height": 74, "weight": 200} for i in range(1, 2001)]
        rows.append({"id": 9001, "firstName": "Arch", "lastName": "Quarterback", "team": "State", "year": 3, "position": "QB", "height": 77, "weight": 225})
        rows.append({"id": 9002, "firstName": "Young", "lastName": "Freshman", "team": "State", "year": 1, "position": "QB", "height": 75, "weight": 210})
        rows.append({"id": 9003, "firstName": "Big", "lastName": "Tackle", "team": "State", "year": 4, "position": "OT", "height": 78, "weight": 315})
        rows.append({"id": 9004, "firstName": "Small", "lastName": "Tackle", "team": "Elsewhere", "year": 4, "position": "OT", "height": 78, "weight": 300})
        return rows
    if path == "/stats/player/season":
        c = params["category"]
        if c == "passing":
            return [{"playerId": p, "player": "x", "team": "State", "category": c, "statType": s, "stat": v} for p in (9001, 9002) for s, v in (("YDS", "2,500"), ("TD", 20), ("INT", 4))]
        if c == "receiving":
            return [{"playerId": 3, "category": c, "statType": s, "stat": v} for s, v in (("REC", 70), ("YDS", 1100), ("TD", 9))]
        return []
    if path == "/teams/fbs":
        return [{"school": "State", "conference": "Big Ten"}, {"school": "Elsewhere", "conference": "Sun Belt"}]


r = draft.build(2026, fake)
names = {p[1]: p for p in r["pool"]}
t("builds an ok pool", r["ok"] and r["v"] == draft.VERSION and len(r["pool"]) == 3)
t("lineman from a big conference is in, a small-conference one is not", "Big Tackle" in names and "Small Tackle" not in names and names["Big Tackle"][9] == 0)
t("QB production is his passing yards", names["Arch Quarterback"][9] == 2500)
t("junior QB is in, freshman is not", "Arch Quarterback" in names and "Young Freshman" not in names)
t("stat line reads well", names["Arch Quarterback"][8] == "2500 pass yds, 20 TD, 4 INT")
t("receiver line and conference", names["P 3"][8] == "70 rec, 1100 yds, 9 TD" and names["P 3"][4] == "Big Ten")
try:
    draft.build(2026, lambda p, q=None: [])
    t("empty roster raises", False)
except draft.ApiError:
    t("empty roster raises", True)
print("ALL PASSED" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
