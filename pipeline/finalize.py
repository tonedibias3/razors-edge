import json, numpy as np, pandas as pd
from sklearn.linear_model import Ridge, LinearRegression
import glob, re
D=""   # run from work/
SEASON,WEEK=(int(x) for x in open("target.txt").read().split())
r=pd.read_pickle("games.pkl"); r["dvp"]=r.dvp.fillna(0); bt=pd.read_pickle("bt.pkl")
FEATS=["ewma","last3","last8","u_attempts","u_carries","u_targets","implied","spread","home","dvp"]
thr={"QB":8,"RB":4,"WR":4,"TE":3}; K=0.5
def shrink(m,e): a=m-e; return e+np.where(a<0,a,a*K)
bt["fin"]=shrink(bt.model,bt.ewma)
hist=r[(~r.future)&(r.n_prior>=3)].dropna(subset=FEATS+["dk"]); hist=hist[hist.ewma>=hist.position.map(thr)]
fut=r[r.future&r.ewma.notna()].copy(); fut[["implied","spread","dvp"]]=fut[["implied","spread","dvp"]].fillna(0)
fut["proj"]=np.nan; fut["floor"]=np.nan; fut["ceil"]=np.nan; fut["basic"]=1
for pos in ["QB","RB","WR","TE"]:
    tr=hist[hist.position==pos]; mu,sd=tr[FEATS].mean(),tr[FEATS].std().replace(0,1)
    m=Ridge(alpha=30).fit((tr[FEATS]-mu)/sd,tr.dk)
    e=bt[bt.position==pos]; res=e.dk-e.fin
    ok=(fut.position==pos)&(fut.n_prior>=3)&(fut.ewma>=thr[pos])
    x=fut[ok]; mod=m.predict((x[FEATS]-mu)/sd)
    fut.loc[ok,"proj"]=shrink(mod,x.ewma.values); fut.loc[ok,"floor"]=fut.loc[ok,"proj"]+res.quantile(.2); fut.loc[ok,"ceil"]=fut.loc[ok,"proj"]+res.quantile(.8); fut.loc[ok,"basic"]=0
low=fut.proj.isna()                        # low-usage or short history: plain recent average, flagged basic
fut.loc[low,"proj"]=fut.loc[low,"ewma"]*0.9; fut.loc[low,"floor"]=(fut.loc[low,"proj"]-3).clip(lower=0); fut.loc[low,"ceil"]=fut.loc[low,"proj"]+6
fut["adj"]=fut.proj-fut.ewma
rows=[[x.player_display_name,x.position,x.team,x.opponent_team,int(x.home) if x.home==x.home else 0,round(x.proj,1),round(x.floor,1),round(x.ceil,1),round(x.ewma,1),round(x.adj,1),round(x.implied,1),round(x.dvp,1),int(x.basic)] for x in fut.itertuples()]

# ---- DST proxy: DK defense scoring built from team stat totals and final scores ----
w=pd.concat([pd.read_csv(f"{D}week_{y}.csv",low_memory=False) for y in sorted(int(re.search(r"week_(\d{4})",f).group(1)) for f in glob.glob("week_*.csv"))],ignore_index=True)
w=w[w.season_type=="REG"]
for c in ["def_sacks","def_interceptions","fumble_recovery_opp","def_tds","special_teams_tds","def_safeties","def_fg_blocks","def_pat_blocks","def_punt_blocks"]: w[c]=w[c].fillna(0)
t=w.groupby(["season","week","team","opponent_team"]).agg(sk=("def_sacks","sum"),it=("def_interceptions","sum"),fr=("fumble_recovery_opp","sum"),td=("def_tds","sum"),st=("special_teams_tds","sum"),sf=("def_safeties","sum"),bl=("def_fg_blocks","sum")).reset_index()
s=pd.read_csv(D+"schedule.csv"); s=s[(s.game_type=="REG")&s.home_score.notna()]
pa=pd.concat([s[["season","week","home_team","away_score"]].rename(columns={"home_team":"team","away_score":"pa"}),s[["season","week","away_team","home_score"]].rename(columns={"away_team":"team","home_score":"pa"})])
t=t.merge(pa,on=["season","week","team"])
bands=lambda p:10 if p==0 else 7 if p<=6 else 4 if p<=13 else 1 if p<=20 else 0 if p<=27 else -1 if p<=34 else -4
t["dst"]=t.sk+2*t.it+2*t.fr+6*(t.td+t.st)+2*t.sf+2*t.bl+t.pa.map(bands)
t["t"]=(t.season-2023)*30+t.week; t=t.sort_values(["team","t"])
t["ewma"]=t.groupby("team").dst.transform(lambda x:x.shift(1).ewm(halflife=4,min_periods=2).mean())
env=r.drop_duplicates(["season","week","team"])[["season","week","team","implied"]]
opp_imp=t.merge(env.rename(columns={"team":"opponent_team","implied":"opp_imp"}),on=["season","week","opponent_team"],how="left")
dd=opp_imp.dropna(subset=["ewma","opp_imp"])
tr=dd[dd.t<dd.t.max()-0]; lm=LinearRegression().fit(tr[["ewma","opp_imp"]],tr.dst)
# quick out-of-sample check on the last 16 weeks
cut=dd.t.max()-16; a=dd[dd.t<cut]; b=dd[dd.t>=cut]; l2=LinearRegression().fit(a[["ewma","opp_imp"]],a.dst)
pm=l2.predict(b[["ewma","opp_imp"]]); print("DST backtest MAE model %.2f vs recent-avg %.2f vs flat %.2f ; coef %s"%(abs(b.dst-pm).mean(),abs(b.dst-b.ewma).mean(),abs(b.dst-a.dst.mean()).mean(),l2.coef_.round(2)))
last=t.groupby("team").tail(8).groupby("team").dst.apply(lambda x:x.ewm(halflife=4).mean().iloc[-1])
fw=r[r.future].drop_duplicates("team")[["team","opponent_team","implied"]]
oppimp=dict(zip(fw.team,fw.implied))
dst=[[x.team,x.opponent_team,round(float(lm.predict(pd.DataFrame({"ewma":[last[x.team]],"opp_imp":[oppimp[x.opponent_team]]}))[0]),1),round(float(last[x.team]),1)] for x in fw.itertuples() if x.team in last.index and x.opponent_team in oppimp]
json.dump({"week":WEEK,"rows":rows,"dst":dst},open("dfs.json","w"),separators=(",",":"))
print(len(rows),"player rows,",sum(1 for x in rows if x[12])," basic;",len(dst),"DST rows | file KB:",round(len(open("dfs.json").read())/1024))
print("sample DST:",sorted(dst,key=lambda x:-x[2])[:4])
