# Razor's Edge

Personal NFL and college football research tool. It is one web page that rebuilds itself and publishes to GitHub Pages.

**What it does**
- **Home** (opens first): buttons to every section plus cards for upcoming games, line moves, open bets, teaser candidates (dogs +1.5 to +2.5, favorites −7.5 to −8.5) and your top 10 draft prospects. Press Edit layout to reorder, hide or bring back any button or card.
- **Draft**: build your own big board (search a prospect pool, paste a list from anywhere, or add by hand), set ranks, tiers and notes, then run a round-1 mock draft in current worst-to-best record order.
- **Lines & teasers** (opens first): every game's spread and total, with how often similar lines covered, team records (and conference records in college), AP ranks, last-10 trends, head-to-head history, and filters and sorts for side (home/road dogs), spread size, kickoff window (early, late, prime time), overs/unders hitting, and line moved. The Teasers page lets you build a slip, compare 6, 6.5 and 7 points, type your book's odds and see the payout, break-even and expected result.
- **Teams** (NFL): best and worst offenses and defenses, sortable both ways.
- **Players, Defenses, Top hit rates** (NFL): prop-bet hit rates by player and by defense, with opponent rank.
- **DFS** (NFL): DraftKings lineup builder with projections.
- **Bets**: track real and practice bets (teasers, parlays, straight bets), with profit, record and grading from final scores.
- **Sync between devices** (Settings): saves your bets, picks, lineups, teasers, draft board and never-play list to a private GitHub Gist in your own account, so every device matches. One-time setup per device: make a GitHub token with only the `gist` permission and paste it in Settings.
- **Saved**: props, picks, lineups and teasers you save. Everything you save or edit lives in your own browser only (it is never sent to GitHub or this repository).

## Where the data comes from
| What | Source | Key needed |
|---|---|---|
| NFL stats, schedule, scores | nflverse / nfldata (free, public) | none |
| College schedule, scores, ranks | CollegeFootballData.com | `CFBD_API_KEY` (free) |
| Draft prospect pool (juniors and seniors with the most production) | CollegeFootballData.com | `CFBD_API_KEY` (same key) |
| Current spreads and totals, plus line history | The Odds API (Bovada first, then DraftKings, FanDuel, BetMGM) | `ODDS_API_KEY` (free plan, 500 credits a month) |

Keys are stored as repository secrets (GitHub: Settings, Secrets and variables, Actions) and read during the build. They are never written into the page. Without a key that part simply stays off and the page keeps working with the free schedule lines.

## When it updates
- Every day around **7:17 am** and **1:17 pm Eastern** (GitHub Actions schedule in `.github/workflows/refresh.yml`).
- Whenever code is pushed, or when you press **Actions, Refresh and publish, Run workflow**.
- Odds credits: a refresh of NFL plus college costs 4 credits, so twice a day is about 240 of the free 500 a month. A run less than 3 hours after the last real fetch reuses the saved lines instead of spending credits (so code pushes don't use up the plan).
- The line history ("was +8.5", the Line moved filter, the movement list on a game) is kept between runs in the GitHub Actions cache. If that cache is ever lost, history simply starts over.
- Lines you type in yourself on a game are saved in your browser and marked with a pencil. A newer line from the feed replaces them.

## Each week (fantasy)
1. Export the DraftKings salary CSV for the slate.
2. Upload it to this repository as `app/DKSalaries.csv` (replace the old file: **Add file, Upload files**, drag it in, commit).
3. The site rebuilds within a few minutes.

You can also just load a CSV on the page itself. That works instantly but only in your own browser.

## How it fits together
- `pipeline/` the data scripts. `python pipeline/run_all.py` runs everything and writes `site/index.html`.
  - `fetch.py` / `prep_data.py` NFL data and projections
  - `college.py` college data (CollegeFootballData)
  - `draft.py` prospect search pool for the Draft board (CollegeFootballData, reused for about a day)
  - `odds.py` current lines and line history (The Odds API)
- `app/` the page (`template.html`), its logic (`core.js`) and the built-in salary file.
- `tests/` `smoke_test.js` runs before every publish (if it fails, the old site stays up); `test_college.py`, `test_odds.py` and `test_draft.py` and `test_cfbstats.py` check the college, odds, draft and college-stats code with made-up data.
- `.github/workflows/refresh.yml` the schedule and the publish steps.

## Run it yourself
```
pip install -r requirements.txt
python pipeline/run_all.py
python tests/test_odds.py
```


### Draft extras
- Browse prospects by position or school (sorted by this season's main stat), share the big board as a PNG (Top 10/25/32), and a mock draft that follows traded 2027 first-round picks (editable with "Edit pick owners").

### Team stats
- Teams tab: offense/defense yards and points per game with rank shading, NFC/AFC and division filter; College (via the League switch) adds a conference filter. College stats come from `pipeline/cfbstats.py` (CollegeFootballData `/games/teams`, FBS opponents only); if that feed fails the page just leaves college stats out.
- Lines tab: a Stats button on each game opens both teams' offense vs defense side by side.
