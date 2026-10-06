"""Checks pipeline/college.py against a pretend CollegeFootballData.com. Run: python tests/test_college.py [out.json]
With an output path it also writes the resulting college section (used to try the page without a real key)."""
import json, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
import college

random.seed(7)
CONFS = {"SEC": 16, "Big Ten": 18, "Big 12": 16, "ACC": 17, "American Athletic": 14, "Conference USA": 10, "Mid-American": 12, "Mountain West": 12, "Sun Belt": 14}
TEAMS = []
for c, n in CONFS.items():
    for i in range(n):
        TEAMS.append((f"{c} U{i}", c))
season = 2026
fake_teams = [{"school": n, "abbreviation": "".join(w[0] for w in n.split()).upper() + str(abs(hash(n)) % 90), "conference": c, "color": "#%06x" % random.randint(0x222222, 0xcccccc), "alternateColor": "#ffffff"} for n, c in TEAMS]


def fake_lines(year):
    out = []
    names = [n for n, _ in TEAMS]
    for wk in range(1, 13):
        random.shuffle(names)
        for i in range(0, 60, 2):
            h, a = names[i], names[i + 1]
            sp = random.choice([-21, -14, -10.5, -7, -3.5, -3, -1, 1, 3, 6.5, 10])
            played = year < season or wk < 6
            hs = random.randint(7, 55) if played else None
            as_ = random.randint(7, 55) if played else None
            fav = h if sp < 0 else a
            fmt = f"{fav} -{abs(sp)}"
            out.append({"id": len(out), "season": year, "week": wk, "startDate": f"{year}-09-{(wk % 28) + 1:02d}T{random.choice([16, 19, 23])}:30:00.000Z", "startTimeTBD": False,
                        "homeTeam": h, "awayTeam": a, "homeScore": hs, "awayScore": as_,
                        "lines": [{"provider": "A", "spread": sp, "formattedSpread": fmt, "overUnder": 52.5}, {"provider": "B", "spread": sp, "formattedSpread": fmt, "overUnder": 53.5}]})
    out.append({"homeTeam": "Some FCS", "awayTeam": names[0], "week": 3, "lines": [{"spread": -3, "formattedSpread": "x -3", "overUnder": 40}]})
    return out


def fake_get(path, params=None):
    if path == "/teams/fbs":
        return fake_teams
    if path == "/lines":
        return fake_lines(params["year"])
    if path == "/rankings":
        return [{"week": w, "polls": [{"poll": "AP Top 25", "ranks": [{"rank": r + 1, "school": TEAMS[r][0]} for r in range(25)]}] } for w in range(1, 7)]
    raise AssertionError(path)


college.get = fake_get
res = college.build(season)
ok = True
def t(name, cond):
    global ok
    print("ok  " if cond else "FAIL", name)
    ok = ok and cond
t("teams loaded", len(res["teams"]) == len(TEAMS))
t("FCS game dropped", all(r[3] in res["teams"] and r[4] in res["teams"] for r in res["sched"]))
t("five seasons of games", {r[0] for r in res["sched"]} == set(range(season - 4, season + 1)))
t("upcoming week found", res["week"] == 6)
t("rankings by week", res["ranks"]["3"][TEAMS[0][0]] == 1)
g = next(r for r in res["sched"] if r[5] is not None)
t("margin = home minus away", g[5] == g[9] - g[8])
# spread convention: "Home -7" must come out as +7 (home favored), "Away -7" as -7
t("home favorite is positive", college.home_spread({"formattedSpread": "Texas -7.5", "spread": -7.5}, "Texas", "Utah") == 7.5)
t("away favorite is negative", college.home_spread({"formattedSpread": "Utah -3", "spread": 3}, "Texas", "Utah") == -3)
t("fallback uses -spread", college.home_spread({"spread": -4}, "A", "B") == 4)
t("pick em", college.home_spread({"formattedSpread": "Texas PK", "spread": 0}, "Texas", "Utah") == 0.0)
t("kickoff in Eastern", college.et_parts("2026-10-10T23:30:00.000Z", False) == ("2026-10-10", "19:30"))
if len(sys.argv) > 1:
    json.dump(res, open(sys.argv[1], "w"), separators=(",", ":"))
sys.exit(0 if ok else 1)
