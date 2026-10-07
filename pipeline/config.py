"""Shared settings. Everything downloaded or generated goes in work/ (not saved to git)."""
import os
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "work")
FIRST_SEASON = 2023


def upcoming(schedule_csv=None, today=None):
    """The current NFL week as (season, week): the first week that still has an unplayed game, or None if the season is finished.
    A week stays "current" until its last game is played, so after Thursday night's game the Sunday slate is still this week.
    A game that has gone unplayed for more than a week (cancelled, say) is ignored so it can't hold the week back forever."""
    s = pd.read_csv(schedule_csv or os.path.join(WORK, "schedule.csv"))
    s = s[s.game_type == "REG"].sort_values(["season", "week"])
    cutoff = (pd.Timestamp(today) if today is not None else pd.Timestamp.now()).normalize() - pd.Timedelta(days=7)
    for (season, week), g in s.groupby(["season", "week"], sort=True):
        if (g.result.isna() & (pd.to_datetime(g.gameday) >= cutoff)).any():
            return int(season), int(week)
    return None
