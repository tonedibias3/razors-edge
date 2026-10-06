"""Shared settings. Everything downloaded or generated goes in work/ (not saved to git)."""
import os
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "work")
FIRST_SEASON = 2023


def upcoming(schedule_csv=None):
    """The next NFL week where no game has been played yet, as (season, week), or None if the schedule is finished."""
    s = pd.read_csv(schedule_csv or os.path.join(WORK, "schedule.csv"))
    s = s[s.game_type == "REG"].sort_values(["season", "week"])
    for (season, week), g in s.groupby(["season", "week"], sort=True):
        if g.result.isna().all():
            return int(season), int(week)
    return None
