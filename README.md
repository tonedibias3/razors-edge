# Razor's Edge

Personal NFL research and daily fantasy tool: player prop hit rates, defense vs position, teaser history, and DraftKings lineup building with projections.

The site rebuilds itself on a schedule (Tue, Wed, Thu and Sat mornings) from free public data (nflverse) and publishes to GitHub Pages.

## Each week
1. Export the DraftKings salary CSV for the slate.
2. Upload it to this repository as `app/DKSalaries.csv` (replace the old file: **Add file → Upload files**, drag it in, commit).
3. The site rebuilds within a few minutes. You can also press **Actions → Refresh and publish → Run workflow**.

You can also just load a CSV on the page itself. That works instantly but only in your own browser.

## How it fits together
- `pipeline/` the data and projection scripts. `python pipeline/run_all.py` runs everything and writes `site/index.html`.
- `app/` the page (`template.html`), its logic (`core.js`) and the built-in salary file.
- `tests/smoke_test.js` runs before every publish. If it fails, the old site stays up.
- `.github/workflows/refresh.yml` the schedule.

## Run it yourself
```
pip install -r requirements.txt
python pipeline/run_all.py
```
