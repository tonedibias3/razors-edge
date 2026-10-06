# Last 10 games for every projected player and defense, written into dfs.json under "logs".
# Player row: [season, week, opp, home, dk points, short stat line]. Key is "name|team" (defenses: "DST|team").
import json, pandas as pd
import glob, re
D = ""   # run from work/
r = pd.read_pickle("games.pkl")
fut = r[r.future & r.ewma.notna()]
keys = {(x.player_id): (x.player_display_name + "|" + x.team) for x in fut.drop_duplicates("player_id").itertuples()}
h = r[~r.future & r.dk.notna() & r.player_id.isin(keys)].sort_values(["player_id", "t"])
n0 = lambda v: 0 if pd.isna(v) else int(round(v))
def line(x):
    pos, parts = x.position, []
    td = n0(x.rushing_tds) + n0(x.receiving_tds)
    if pos == "QB":
        parts.append(f"{n0(x.completions)}/{n0(x.attempts)}, {n0(x.passing_yards)} yds")
        if n0(x.passing_tds): parts.append(f"{n0(x.passing_tds)} TD")
        if n0(x.passing_interceptions): parts.append(f"{n0(x.passing_interceptions)} INT")
        if n0(x.carries) >= 3 or n0(x.rushing_tds): parts.append(f"{n0(x.carries)} car {n0(x.rushing_yards)} yds" + (f", {n0(x.rushing_tds)} TD" if n0(x.rushing_tds) else ""))
    elif pos == "RB":
        parts.append(f"{n0(x.carries)} car {n0(x.rushing_yards)} yds")
        if n0(x.targets) or n0(x.receptions): parts.append(f"{n0(x.receptions)} rec {n0(x.receiving_yards)} yds")
        if td: parts.append(f"{td} TD")
    else:
        parts.append(f"{n0(x.receptions)} rec {n0(x.receiving_yards)} yds ({n0(x.targets)} tgt)")
        if td: parts.append(f"{td} TD")
        if n0(x.carries): parts.append(f"{n0(x.carries)} car {n0(x.rushing_yards)} yds")
    return " · ".join(parts)
logs = {}
for pid, g in h.groupby("player_id"):
    logs[keys[pid]] = [[int(x.season), int(x.week), x.opponent_team, int(x.home) if x.home == x.home else 0, round(float(x.dk), 1), line(x)] for x in g.tail(10).itertuples()]
# defenses, same scoring as the projection proxy
w = pd.concat([pd.read_csv(f"{D}week_{y}.csv", low_memory=False) for y in sorted(int(re.search(r"week_(\d{4})", f).group(1)) for f in glob.glob("week_*.csv"))], ignore_index=True)
w = w[w.season_type == "REG"]
for c in ["def_sacks", "def_interceptions", "fumble_recovery_opp", "def_tds", "special_teams_tds", "def_safeties", "def_fg_blocks"]: w[c] = w[c].fillna(0)
t = w.groupby(["season", "week", "team", "opponent_team"]).agg(sk=("def_sacks", "sum"), it=("def_interceptions", "sum"), fr=("fumble_recovery_opp", "sum"), td=("def_tds", "sum"), st=("special_teams_tds", "sum"), sf=("def_safeties", "sum"), bl=("def_fg_blocks", "sum")).reset_index()
s = pd.read_csv(D + "schedule.csv"); s = s[(s.game_type == "REG") & s.home_score.notna()]
pa = pd.concat([s[["season", "week", "home_team", "away_score"]].rename(columns={"home_team": "team", "away_score": "pa"}).assign(home=1), s[["season", "week", "away_team", "home_score"]].rename(columns={"away_team": "team", "home_score": "pa"}).assign(home=0)])
t = t.merge(pa, on=["season", "week", "team"])
bands = lambda p: 10 if p == 0 else 7 if p <= 6 else 4 if p <= 13 else 1 if p <= 20 else 0 if p <= 27 else -1 if p <= 34 else -4
t["dst"] = t.sk + 2 * t.it + 2 * t.fr + 6 * (t.td + t.st) + 2 * t.sf + 2 * t.bl + t.pa.map(bands)
t = t.sort_values(["team", "season", "week"])
for team, g in t.groupby("team"):
    logs["DST|" + team] = [[int(x.season), int(x.week), x.opponent_team, int(x.home), float(x.dst), f"{int(x.pa)} pts allowed · {int(x.sk)} sk · {int(x.it)} int · {int(x.fr)} fr" + (f" · {int(x.td + x.st)} TD" if x.td + x.st else "")] for x in g.tail(10).itertuples()]
j = json.load(open("dfs.json")); j["logs"] = logs
json.dump(j, open("dfs.json", "w"), separators=(",", ":"))
print(len(logs), "logs | KB:", round(len(open("dfs.json").read()) / 1024))
