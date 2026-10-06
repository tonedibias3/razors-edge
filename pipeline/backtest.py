import numpy as np, pandas as pd
from sklearn.linear_model import Ridge
r = pd.read_pickle("games.pkl")
r["dvp"] = r.dvp.fillna(0)
FEATS = ["ewma","last3","last8","u_attempts","u_carries","u_targets","implied","spread","home","dvp"]
d = r[(r.n_prior>=3)].dropna(subset=FEATS+["dk"]).copy()
# DFS-relevant players only: typical recent output
thr = {"QB":8,"RB":4,"WR":4,"TE":3}
d = d[d.ewma >= d.position.map(thr)]
tests = sorted(d.t.unique())[-20:]   # the 20 most recent weeks
out=[]
for t in tests:
    for pos in ["QB","RB","WR","TE"]:
        tr = d[(d.t<t)&(d.position==pos)]; te = d[(d.t==t)&(d.position==pos)]
        if len(te)==0: continue
        mu, sd = tr[FEATS].mean(), tr[FEATS].std().replace(0,1)
        m = Ridge(alpha=30).fit((tr[FEATS]-mu)/sd, tr.dk)
        te = te.copy(); te["model"] = m.predict((te[FEATS]-mu)/sd); out.append(te)
res = pd.concat(out)
def stats(col, g):
    e = g.dk-g[col]
    return pd.Series({"MAE":e.abs().mean(),"RMSE":np.sqrt((e**2).mean()),"corr":np.corrcoef(g[col],g.dk)[0,1],"bias":-e.mean()})
rows=[]
for pos,g in list(res.groupby("position"))+[("ALL",res)]:
    for col in ["last3","ewma","model"]:
        rows.append(pd.concat([pd.Series({"pos":pos,"pred":col,"n":len(g)}),stats(col,g)]))
tab=pd.DataFrame(rows); print(tab.round(3).to_string(index=False))
# the question that matters for lineups: of each week's top-N projected, how many actual points?
def topn(col,n):
    v=[]
    for (t,pos),g in res.groupby(["t","position"]):
        k={"QB":n["QB"],"RB":n["RB"],"WR":n["WR"],"TE":n["TE"]}[pos]
        v.append(g.nlargest(k,col).dk.mean())
    return np.mean(v)
N={"QB":3,"RB":8,"WR":12,"TE":4}
print("\navg actual points of each week's top-N projected (QB3 RB8 WR12 TE4):", {c:round(topn(c,N),2) for c in ["last3","ewma","model"]})
res.to_pickle("bt.pkl")
print("test weeks:", len(tests), "player-games:", len(res))
