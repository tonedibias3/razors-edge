"""Download the free public NFL data (nflverse) into work/: weekly player stats and the schedule with betting lines."""
import os, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from config import WORK, FIRST_SEASON, upcoming

STATS = "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{y}.csv"
TEAM = "https://github.com/nflverse/nflverse-data/releases/download/stats_team/stats_team_week_{y}.csv"
SCHED = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"


def get(url, dest, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(dest + ".tmp", "wb") as f:
                f.write(r.read())
            os.replace(dest + ".tmp", dest)
            return True
        except Exception as e:  # 404 for a season that has not started is expected
            err = e
            if getattr(e, "code", None) == 404:
                break
            time.sleep(5 * (i + 1))
    print("could not download", url, "->", err)
    return False


if __name__ == "__main__":
    os.makedirs(WORK, exist_ok=True)
    assert get(SCHED, os.path.join(WORK, "schedule.csv")), "schedule download failed"
    nxt = upcoming()
    if nxt is None:
        sys.exit("The schedule has no unplayed weeks left. Nothing to project.")
    season, week = nxt
    got = []
    for y in range(FIRST_SEASON, season + 1):
        get(TEAM.format(y=y), os.path.join(WORK, f"team_{y}.csv"))   # team yardage; the page copes if one is missing
        ok = get(STATS.format(y=y), os.path.join(WORK, f"week_{y}.csv"))
        if ok:
            got.append(y)
        elif y < season:
            sys.exit(f"missing stats for {y}")
    open(os.path.join(WORK, "target.txt"), "w").write(f"{season} {week}\n")
    print(f"Projecting {season} week {week}. Stats seasons: {got}")
