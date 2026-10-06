"""DraftKings points per player-game plus pre-game features (only information known before kickoff)."""
import numpy as np, pandas as pd
import os, glob, re
D = ""   # run from work/
SEASON, FUTURE = (int(x) for x in open("target.txt").read().split())
SEASONS = sorted(int(re.search(r"week_(\d{4})", f).group(1)) for f in glob.glob("week_*.csv"))
raw = pd.concat([pd.read_csv(f"{D}week_{y}.csv", low_memory=False) for y in SEASONS], ignore_index=True)
raw = raw[raw.position.isin(["QB", "RB", "WR", "TE"]) & (raw.season_type == "REG")].copy()
num = ["attempts","carries","targets","passing_yards","passing_tds","passing_interceptions","rushing_yards","rushing_tds",
       "receptions","receiving_yards","receiving_tds","sack_fumbles_lost","rushing_fumbles_lost","receiving_fumbles_lost",
       "passing_2pt_conversions","rushing_2pt_conversions","receiving_2pt_conversions","special_teams_tds","fumble_recovery_tds"]
raw[num] = raw[num].fillna(0)
r = raw
r["dk"] = (0.04*r.passing_yards + 4*r.passing_tds - r.passing_interceptions + 3*(r.passing_yards>=300)
           + 0.1*r.rushing_yards + 6*r.rushing_tds + 3*(r.rushing_yards>=100)
           + r.receptions + 0.1*r.receiving_yards + 6*r.receiving_tds + 3*(r.receiving_yards>=100)
           - r.sack_fumbles_lost - r.rushing_fumbles_lost - r.receiving_fumbles_lost
           + 6*(r.special_teams_tds + r.fumble_recovery_tds) + 2*(r.passing_2pt_conversions + r.rushing_2pt_conversions + r.receiving_2pt_conversions))
r = r[(r.attempts>0)|(r.carries>0)|(r.targets>0)].copy()
r["t"] = (r.season-2023)*30 + r.week          # time index
r = r.sort_values(["player_id","t"]).reset_index(drop=True)

# Week-5 placeholders: one empty row per player active this season, tagged with that week's opponent.
_sch = pd.read_csv(D+"schedule.csv"); _sch = _sch[(_sch.season==SEASON)&(_sch.week==FUTURE)&(_sch.game_type=="REG")]
_opp = {}
for g_ in _sch.itertuples():
    _opp[g_.home_team] = g_.away_team; _opp[g_.away_team] = g_.home_team
_last = r.sort_values("t").groupby("player_id").tail(1)
_last = _last[(_last.season>=SEASON-(1 if FUTURE==1 else 0))&_last.team.isin(_opp)].copy()
_fut = _last[["player_id","player_display_name","position","team","season"]].copy()
_fut["week"] = FUTURE; _fut["opponent_team"] = _fut.team.map(_opp); _fut["t"] = (SEASON-2023)*30 + FUTURE; _fut["future"] = True
r["future"] = False
r = pd.concat([r, _fut], ignore_index=True).sort_values(["player_id","t"]).reset_index(drop=True)

# game environment from the schedule: implied team total, spread, home
s = pd.read_csv(D+"schedule.csv"); s = s[s.game_type=="REG"]
rows=[]
for g in s.itertuples():
    tot, sp = g.total_line, g.spread_line      # spread_line > 0 means the home team is favored
    if pd.isna(tot) or pd.isna(sp): continue
    rows.append((g.season,g.week,g.home_team,(tot+sp)/2,sp,tot,1))
    rows.append((g.season,g.week,g.away_team,(tot-sp)/2,-sp,tot,0))
env = pd.DataFrame(rows, columns=["season","week","team","implied","spread","total","home"])
r = r.merge(env, on=["season","week","team"], how="left")

# defense vs position: points allowed per team-game to each position, rolling over the defense's previous 8 games
dv = r.groupby(["season","week","t","opponent_team","position"]).dk.sum().reset_index().rename(columns={"opponent_team":"defn"})
dv = dv.sort_values(["defn","position","t"])
dv["allowed_prior"] = dv.groupby(["defn","position"]).dk.transform(lambda x: x.shift(1).rolling(8, min_periods=3).mean())
lg = dv.groupby(["position","t"]).dk.mean().reset_index().rename(columns={"dk":"lg"})
lg = lg.sort_values(["position","t"]); lg["lg_prior"] = lg.groupby("position").lg.transform(lambda x: x.shift(1).rolling(8, min_periods=3).mean())
dv = dv.merge(lg[["position","t","lg_prior"]], on=["position","t"])
dv["dvp"] = dv.allowed_prior - dv.lg_prior
r = r.merge(dv[["t","defn","position","dvp"]].rename(columns={"defn":"opponent_team"}), on=["t","opponent_team","position"], how="left")

# player history features, strictly from earlier games
g = r.groupby("player_id")
r["n_prior"] = g.cumcount()
r["ewma"]   = g.dk.transform(lambda x: x.shift(1).ewm(halflife=3, min_periods=1).mean())
r["last3"]  = g.dk.transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
r["last8"]  = g.dk.transform(lambda x: x.shift(1).rolling(8, min_periods=1).mean())
for c in ["attempts","carries","targets"]:
    r["u_"+c] = g[c].transform(lambda x: x.shift(1).ewm(halflife=3, min_periods=1).mean())
r.to_pickle("games.pkl")
print(r.shape, "| DK points mean by pos:\n", r.groupby("position").dk.describe()[["count","mean","50%","max"]])
print("env missing:", r.implied.isna().sum(), "| dvp missing:", r.dvp.isna().sum())
