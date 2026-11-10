# Cricket Insights

Search any cricket player, ground, team or match and get pitch behaviour, phase-by-phase stats,
how batters get out, which bowler types take wickets, and full match scorecards with charts.

* Data: men's IPL, T20I, ODI and Test ball-by-ball data from [Cricsheet](https://cricsheet.org) (ODC-BY),
  bowling styles and full names from Wikipedia/Wikidata.
* Updates itself every day: `.github/workflows/build.yml` downloads the latest Cricsheet files,
  rebuilds every page in `site/data/` and publishes to GitHub Pages. Run it by hand from the Actions tab
  ("Update and publish" → Run workflow); a manual run also refreshes bowling styles.
* `pipeline/`: `parse.py` (ball-by-ball → tables), `styles.py` (bowler types), `stats.py` (ground, phase,
  bowler-type and player insights), `build_site.py` (one JSON per player/ground/team/match + search index).
* `site/`: the website (plain HTML/JS, Chart.js).
