"""Trim nflverse weekly player stats into one compact data.json for the hit-rate page.

Run again after each NFL week (re-download the week_YYYY.csv files first) to refresh.
"""
import json
import pandas as pd

import glob, re
SEASONS = sorted(int(re.search(r"week_(\d{4})", f).group(1)) for f in glob.glob("week_*.csv"))
COLS = [
    "player_id", "player_display_name", "position", "season", "week", "season_type",
    "game_id", "team", "opponent_team",
    "attempts", "carries", "targets",
    "passing_yards", "passing_tds", "rushing_yards", "receiving_yards", "receptions",
    "rushing_tds", "receiving_tds",
]

frames = [pd.read_csv(f"week_{y}.csv", usecols=COLS, low_memory=False) for y in SEASONS]
df = pd.concat(frames, ignore_index=True)

df = df[df["position"].isin(["QB", "RB", "WR", "TE"])].copy()

# A game counts for a player only if he had offensive involvement (a pass attempt,
# carry or target). This drops QB2s who only held for field goals, etc.
used = (df["attempts"] > 0) | (df["carries"] > 0) | (df["targets"] > 0)
df = df[used].copy()

# nflverse game_id looks like 2024_01_AWAY_HOME
df["home"] = (df["team"] == df["game_id"].str.split("_").str[3]).astype(int)
df["stype"] = (df["season_type"] == "POST").astype(int)

df = df.sort_values(["player_id", "season", "week"])
dupes = df.duplicated(["player_id", "season", "week"]).sum()
print("duplicate player-weeks:", dupes)

# ---- Defense view: the top players per offense per game, tagged with the defense they faced ----
# Each row is kept once per usage family: p = passing (ranked by attempts), r = rushing
# (ranked by carries), c = catching (ranked by targets). A back can appear in both r and c.
base = df.copy()
for c in ["attempts", "carries", "targets", "passing_yards", "passing_tds",
          "rushing_yards", "receiving_yards", "receptions", "rushing_tds", "receiving_tds"]:
    base[c] = base[c].fillna(0)
specs = [  # position, family, usage column, minimum usage, how many ranks to keep
    ("QB", "p", "attempts", 10, 1),
    ("RB", "r", "carries", 5, 2),
    ("RB", "c", "targets", 1, 2),
    ("WR", "c", "targets", 1, 3),
    ("TE", "c", "targets", 1, 1),
]
parts = []
for pos, fam, use, minv, topn in specs:
    sub = base[(base["position"] == pos) & (base[use] >= minv)].copy()
    sub["rk"] = sub.groupby(["season", "week", "team"])[use].rank(method="first", ascending=False).astype(int)
    sub = sub[sub["rk"] <= topn].copy()
    sub["fam"] = fam
    parts.append(sub)
dd = pd.concat(parts).sort_values(["season", "week", "opponent_team", "position", "fam", "rk"])
def_rows = [
    [int(r.season), int(r.week), int(r.stype), r.opponent_team, r.position, int(r.rk),
     int(r.passing_yards), int(r.passing_tds), int(r.rushing_yards), int(r.receiving_yards),
     int(r.receptions), r.player_display_name, r.team, r.fam,
     int(r.rushing_tds + r.receiving_tds)]
    for r in dd.itertuples()
]
print("defense rows:", len(def_rows), "| defenses:", dd["opponent_team"].nunique())

# Only players with a game in 2024 or later are searchable (older ones can't have a live prop).
last_season = df.groupby("player_id")["season"].max()
keep = last_season[last_season >= 2024].index
df = df[df["player_id"].isin(keep)]

num = ["attempts", "carries", "targets", "passing_yards", "passing_tds",
       "rushing_yards", "receiving_yards", "receptions", "rushing_tds", "receiving_tds"]
df[num] = df[num].fillna(0)

players, games = [], {}
for pid, g in df.groupby("player_id", sort=False):
    last = g.iloc[-1]
    players.append([pid, last["player_display_name"], last["position"], last["team"]])
    games[pid] = [
        [int(r.season), int(r.week), int(r.stype), r.team, r.opponent_team, int(r.home),
         int(r.passing_yards), int(r.passing_tds), int(r.rushing_yards),
         int(r.receiving_yards), int(r.receptions),
         int(r.attempts), int(r.carries), int(r.targets),
         int(r.rushing_tds + r.receiving_tds), int(r.carries + r.targets)]
        for r in g.itertuples()
    ]

players.sort(key=lambda p: p[1])
latest = df[df["season"] == df["season"].max()]

# Next unplayed regular-season game for each team, from the nflverse schedule.
# A game counts as played when the team already has stat rows for that week.
sched = pd.read_csv("schedule.csv")
sched = sched[(sched["season"] == int(df["season"].max())) & (sched["game_type"] == "REG")]
played = set(zip(latest[latest["stype"] == 0]["team"], latest[latest["stype"] == 0]["week"]))
next_game = {}
for r in sched.sort_values(["week", "gameday"]).itertuples():
    for team, opp, home in ((r.away_team, r.home_team, 0), (r.home_team, r.away_team, 1)):
        if team not in next_game and (team, r.week) not in played:
            next_game[team] = {"week": int(r.week), "opp": opp, "home": home, "date": str(r.gameday)}
print("next games found for", len(next_game), "teams; e.g. ATL:", next_game.get("ATL"), "| CAR:", next_game.get("CAR"))

# Every game since 2015 with the book spread and total (for the Teasers tab).
# spread_line is how many points the HOME team is favored by (negative = home underdog).
sg = pd.read_csv("schedule.csv")
sg = sg[(sg["season"] >= 2015) & (sg["game_type"] == "REG")].sort_values(["season", "week", "gameday"])
def _n(v):
    return None if pd.isna(v) else float(v)
sched_rows = [[int(r.season), int(r.week), str(r.gameday), r.away_team, r.home_team, _n(r.result), _n(r.spread_line), _n(r.total_line), _n(r.away_score), _n(r.home_score), ("" if pd.isna(r.gametime) else str(r.gametime))] for r in sg.itertuples()]

# Team yardage per game (offense; a defense's numbers are its opponent's offense in the same game).
# Pass yards are NET of sacks (gross minus sack yards), the way the NFL lists team passing and total yards.
tstats = []
for f in sorted(glob.glob("team_*.csv")):
    t = pd.read_csv(f, usecols=["season", "week", "team", "season_type", "opponent_team", "passing_yards", "sack_yards_lost", "rushing_yards", "attempts", "carries", "sacks_suffered"], low_memory=False)
    t = t[t["season_type"] == "REG"].dropna(subset=["opponent_team"])
    for r in t.itertuples():
        tstats.append([int(r.season), int(r.week), r.team, r.opponent_team, int(r.passing_yards - r.sack_yards_lost), int(r.rushing_yards), int(r.attempts), int(r.carries), int(r.sacks_suffered)])
print("team-game rows:", len(tstats))

out = {
    "tstats": tstats,
    "season": int(df["season"].max()),
    "through_week": int(latest[latest["stype"] == 0]["week"].max()),
    "players": players,
    "games": games,
    "def": def_rows,
    "next": next_game,
    "sched": sched_rows,
}
with open("data.json", "w") as f:
    json.dump(out, f, separators=(",", ":"))

print("players:", len(players), "game rows:", int(df.shape[0]))
print("through:", out["season"], "week", out["through_week"])

# Coverage check: how many teams have a row in each 2026 regular-season week
cov = latest[latest["stype"] == 0].groupby("week")["team"].nunique()
print("teams with offensive rows per 2026 week:\n", cov.to_string())
