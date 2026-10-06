# Points each defense allowed to each position over its last 8 games, vs the league's average over the same weeks.
# Same definition the projection model uses. Writes the table into dfs.json for all 32 teams.
import pandas as pd, json
r = pd.read_pickle("games.pkl")
d = r[~r.future & r.dk.notna()]
dv = d.groupby(["t", "opponent_team", "position"]).dk.sum().reset_index().rename(columns={"opponent_team": "defn"})
out = {}
for pos in ["QB", "RB", "WR", "TE"]:
    x = dv[dv.position == pos]
    lg = x.groupby("t").dk.mean().sort_index()
    league = lg.iloc[-8:].mean()
    out[pos] = {}
    for team, g in x.groupby("defn"):
        g = g.sort_values("t")
        out[pos][team] = round(float(g.dk.iloc[-8:].mean() - league), 2)
# check against what the model used for this week's opponents
f = r[r.future & r.dvp.notna()].groupby(["opponent_team", "position"]).dvp.first()
diff = [abs(out[p][t] - v) for (t, p), v in f.items() if p in out and t in out[p]]
print("teams per position:", {p: len(v) for p, v in out.items()}, "| max diff vs model dvp:", round(max(diff), 2), "| mean:", round(sum(diff) / len(diff), 2))
j = json.load(open("dfs.json")); j["dvp"] = out
json.dump(j, open("dfs.json", "w"), separators=(",", ":"))
