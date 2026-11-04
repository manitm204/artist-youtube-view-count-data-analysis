# Music Artist YouTube Views

Analyzes daily YouTube Charts views by artist: which days peak, how the week
builds, and what the weekly high is likely to be. Started as research for
Kalshi "highest daily view count" markets.

Open [`dashboard/index.html`](dashboard/index.html) in a browser to use the
analysis page. It's also published privately at
<https://claude.ai/artifact/72LM9WzTCEwmHaP7agQoo6>.

## Project layout

```
.
├── dashboard/
│   ├── template.html      Edit this: the page's layout, charts and math
│   └── index.html         Generated page; don't edit by hand
├── data/
│   └── charts/            One CSV per artist: date, global_views
├── scripts/
│   └── build_dashboard.py Builds the page from data/charts
├── archive/               Old scripts, kept for reference only
├── .env.example           Template for a YouTube API key
└── requirements.txt       Packages for the archived regression script
```

## Common tasks

Building the dashboard only needs Python 3.

**Add an artist.** Paste the data into `data/charts/<artist_name>.csv` with the
columns `date,global_views`, then rebuild. The file name becomes the display
name, so `bad_bunny.csv` shows as "Bad Bunny". For a name like SZA, add it to
`DISPLAY_NAMES` in `scripts/build_dashboard.py`.

```
python3 scripts/build_dashboard.py
```

**Add new days for an artist.** Paste the new rows at the end of that artist's
CSV and rebuild.

**Change the page.** Edit `dashboard/template.html` and rebuild. Changes made
directly to `index.html` are overwritten on the next build.

## Data

Everything in `data/charts/` is YouTube Charts Global views pasted from ChatGPT.
The figures haven't been independently verified.

## Good to know

- **Don't scrape YouTube Charts.** YouTube's terms ban automated access and
  `robots.txt` disallows `/youtubei/`, the endpoint the charts load from. That's
  why `archive/drake_youtube_views.py` is out of use.
- **The other archived scripts won't run as they are.**
  `archive/track_drake_views.py` and `archive/run_drake_regression.py` used a
  `data/drake/` folder that has since been removed.
- **Charts are rate-limited on this network.** The page opens blank with a 429
  response in a normal browser too. Copying numbers by hand from another network
  is fine.
- **Weekly stats use full Monday to Sunday weeks only.** The week of Oct 5 has no
  Monday, and it also had a new Drake release.
- **The sample is small.** There are only a few full weeks so far, and a new
  release can break the pattern.
- **`.env` holds an API key.** It's in `.gitignore`, so don't commit or share it.
