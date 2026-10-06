"""Current NFL and college spreads and totals from The Odds API (the-odds-api.com), saved with a history so the page can show line movement.
Updates the betting lines in work/data.json for games that have not been played, and adds an "odds" section.
It never stops the build: with no key, or if the service is down, the lines from the free schedule files stay as they are.
Free plan = 500 credits a month. One refresh of NFL + college costs 4 credits (2 sports x spreads+totals), so twice a day is about 240 a month.
A run less than MIN_GAP_HOURS after the last real fetch reuses the saved lines instead of spending credits (so code pushes don't burn the plan)."""
import json, os, re, sys, time, unicodedata, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(__file__))
from config import WORK

KEY = os.environ.get("ODDS_API_KEY", "").strip()
BASE = "https://api.the-odds-api.com/v4"
SPORTS = {"nfl": "americanfootball_nfl", "cfb": "americanfootball_ncaaf"}
BOOKS = ["bovada", "draftkings", "fanduel", "betmgm"]            # first one that has the market wins; Bovada is the one you bet on
BOOK_NAMES = {"bovada": "Bovada", "draftkings": "DraftKings", "fanduel": "FanDuel", "betmgm": "BetMGM"}
MIN_GAP_HOURS = float(os.environ.get("ODDS_MIN_GAP_HOURS", "3"))
CACHE = os.environ.get("ODDS_CACHE") or os.path.join(WORK, "odds_cache")
ET = ZoneInfo("America/New_York")
KEEP_DAYS = 21

NFL_NAMES = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF", "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI", "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL", "Denver Broncos": "DEN",
    "Detroit Lions": "DET", "Green Bay Packers": "GB", "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC", "Los Angeles Rams": "LA", "Los Angeles Chargers": "LAC", "Las Vegas Raiders": "LV", "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN", "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG", "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT", "Seattle Seahawks": "SEA", "San Francisco 49ers": "SF", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]", "", s.lower().replace("&", " and ").replace("'", "")).strip()


def get(path, params):
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "razors-edge"}), timeout=60) as r:
                return json.loads(r.read().decode("utf-8")), r.headers.get("x-requests-remaining")
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise RuntimeError(f"The Odds API rejected the key (HTTP {e.code}). Check the ODDS_API_KEY secret.")
            if e.code == 429:
                raise RuntimeError("The Odds API says the monthly credits are used up (HTTP 429). Lines keep their last saved values until it resets.")
            last = e; time.sleep(3 * (attempt + 1))
        except Exception as e:
            last = e; time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"could not reach The Odds API ({last})")


def parse_event(ev):
    """One event -> (home_name, away_name, commence datetime, home_spread_point or None, total or None, book keys used)."""
    home, away = ev.get("home_team"), ev.get("away_team")
    by = {b.get("key"): b for b in ev.get("bookmakers", [])}
    sp = tot = None; used = []
    for k in BOOKS:
        b = by.get(k)
        if not b: continue
        for m in b.get("markets", []):
            if m.get("key") == "spreads" and sp is None:
                o = next((x for x in m.get("outcomes", []) if x.get("name") == home and x.get("point") is not None), None)
                if o: sp = float(o["point"]); used.append(k)
            elif m.get("key") == "totals" and tot is None:
                o = next((x for x in m.get("outcomes", []) if str(x.get("name")).lower() == "over" and x.get("point") is not None), None)
                if o: tot = float(o["point"]); used.append(k)
    try:
        when = datetime.fromisoformat(str(ev.get("commence_time")).replace("Z", "+00:00"))
    except Exception:
        when = None
    return home, away, when, sp, tot, used


def team_resolver(lg, teams):
    if lg == "nfl":
        return lambda name: NFL_NAMES.get(name)
    table = sorted(((norm(t), t) for t in teams), key=lambda x: -len(x[0]))   # longest school name first, so "Miami (OH)" beats "Miami"
    cache = {}
    def f(name):
        if name in cache: return cache[name]
        n = norm(name); hit = None
        for nt, t in table:
            if n == nt or n.startswith(nt + " "):
                hit = t; break
        cache[name] = hit
        return hit
    return f


def apply_lines(lg, sched, season, resolve, events, now_ts, state):
    """Writes the new lines into the schedule rows (upcoming games only) and updates history. Returns (matched, upcoming, book counts)."""
    idx = {}
    for r in sched:
        if r[0] == season and r[5] is None:
            idx.setdefault((r[3], r[4]), []).append(r)
    hist = state["history"].setdefault(lg, {})
    latest = state["latest"].setdefault(lg, {})
    matched = 0; books = {}
    for ev in events:
        home, away, when, sp, tot, used = parse_event(ev)
        h, a = resolve(home), resolve(away)
        if not h or not a or (sp is None and tot is None) or when is None: continue
        d = when.astimezone(ET).date()
        row = next((r for r in idx.get((a, h), []) if abs((datetime.fromisoformat(r[2]).date() - d).days) <= 1), None)
        if not row: continue
        s = -sp if sp is not None else row[6]
        t = tot if tot is not None else row[7]
        k = f"{row[0]}|{row[1]}|{row[3]}|{row[4]}"
        latest[k] = [s, t, now_ts]
        h_ = hist.setdefault(k, [])
        if not h_ or h_[-1][1] != s or h_[-1][2] != t:
            h_.append([now_ts, s, t])
        for u in set(used): books[u] = books.get(u, 0) + 1
        matched += 1
    return matched, sum(len(v) for v in idx.values()), books


def reapply_saved(lg, sched, season, state):
    n = 0
    for r in sched:
        if r[0] == season and r[5] is None:
            v = state["latest"].get(lg, {}).get(f"{r[0]}|{r[1]}|{r[3]}|{r[4]}")
            if v:
                r[6], r[7] = v[0], v[1]; n += 1
    return n


def write_back(lg, sched, season, state):
    """Put the saved lines into the schedule rows."""
    return reapply_saved(lg, sched, season, state)


def prune(state, now):
    cutoff = now - KEEP_DAYS * 86400
    for lg in list(state["history"]):
        for k in list(state["history"][lg]):
            if state["history"][lg][k][-1][0] < cutoff:
                del state["history"][lg][k]; state["latest"].get(lg, {}).pop(k, None)


def run(data, now=None, fetch=None, key=KEY):
    now = now or time.time()
    os.makedirs(CACHE, exist_ok=True)
    sp = os.path.join(CACHE, "state.json")
    try:
        state = json.load(open(sp))
    except Exception:
        state = {}
    state.setdefault("history", {}); state.setdefault("latest", {}); state.setdefault("updated", {}); state.setdefault("books", {}); state.setdefault("last_fetch", 0); state.setdefault("matched", {})
    if not key:
        data["odds"] = {"ok": False, "reason": "No ODDS_API_KEY secret is set in the repository."}
        return data
    leagues = {"nfl": (data["sched"], int(data["season"]))}
    col = data.get("college") or {}
    if col.get("ok"):
        leagues["cfb"] = (col["sched"], int(col["season"]))
    fresh = (now - state["last_fetch"]) < MIN_GAP_HOURS * 3600
    err = None; credits = state.get("credits")
    if not fresh:
        fetch = fetch or (lambda sport: get(f"/sports/{sport}/odds", {"apiKey": key, "bookmakers": ",".join(BOOKS), "markets": "spreads,totals", "oddsFormat": "american", "dateFormat": "iso"}))
        any_ok = False
        for lg, (sched, season) in leagues.items():
            try:
                events, rem = fetch(SPORTS[lg])
                if rem is not None: credits = rem
                resolve = team_resolver(lg, (col.get("teams") or {}).keys() if lg == "cfb" else [])
                m, up, books = apply_lines(lg, sched, season, resolve, events or [], now, state)
                state["updated"][lg] = now; state["books"][lg] = books; state["matched"][lg] = [m, up]; any_ok = True
                print(f"odds: {lg}: {m} of {up} upcoming games matched, books {books}, credits left {rem}")
            except Exception as e:
                err = str(e)[:300]; print(f"odds: {lg} FAILED ({err})")
        if any_ok: state["last_fetch"] = now
        if credits is not None: state["credits"] = credits
    else:
        print(f"odds: last fetch was {(now - state['last_fetch']) / 3600:.1f}h ago, reusing saved lines (no credits used)")
    prune(state, now)
    for lg, (sched, season) in leagues.items():
        n = write_back(lg, sched, season, state)
    json.dump(state, open(sp, "w"), separators=(",", ":"))
    iso = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data["odds"] = {"ok": bool(state["updated"]), "updated": {lg: iso(t) for lg, t in state["updated"].items() if lg in leagues},
                    "books": {lg: {BOOK_NAMES.get(k, k): v for k, v in b.items()} for lg, b in state["books"].items() if lg in leagues},
                    "matched": {lg: v for lg, v in state["matched"].items() if lg in leagues}, "credits": state.get("credits"),
                    "moves": {lg: {k: v for k, v in h.items()} for lg, h in state["history"].items() if lg in leagues}}
    if err: data["odds"]["error"] = err
    if not state["updated"] and not err: data["odds"]["reason"] = "No lines saved yet."
    return data


if __name__ == "__main__":
    path = os.path.join(WORK, "data.json")
    data = json.load(open(path))
    try:
        run(data)
    except Exception as e:  # never block the site
        print("odds: FAILED (site will build with the schedule lines):", str(e)[:300])
        data["odds"] = {"ok": False, "reason": str(e)[:300]}
    json.dump(data, open(path, "w"), separators=(",", ":"))
