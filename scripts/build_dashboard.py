"""Build dashboard/index.html from every CSV in data/charts.

To add an artist, save data/charts/<artist_name>.csv and rerun this script. The
file name becomes the display name, so bad_bunny.csv shows as "Bad Bunny".
"""

import argparse
import csv
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHARTS_DIR = ROOT / "data" / "charts"
TEMPLATE = ROOT / "dashboard" / "template.html"
OUTPUT = ROOT / "dashboard" / "index.html"

# Only needed when title case gets a name wrong, such as {"sza": "SZA"}.
DISPLAY_NAMES = {}

# Cells that mean "no data for this day", such as a blip in the source. They
# become null on the page, which leaves the day out instead of guessing it.
MISSING = {"", "nan", "null", "none", "na", "n/a", "-"}

PAGE_START = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>body { margin: 0; } [hidden] { display: none !important; }</style>
</head>
<body>
"""
PAGE_END = "</body>\n</html>\n"


def parse_views(raw, path, line):
    text = (raw or "").strip()
    if text.lower() in MISSING:
        return None
    try:
        return int(text.replace(",", ""))
    except ValueError:
        raise SystemExit(f"{path.name} line {line}: {raw!r} isn't a whole number or a missing-value marker such as NaN.")


def read_artist(path):
    slug = path.stem
    views_by_date = {}
    with path.open(newline="", encoding="utf-8") as csv_file:
        for line, row in enumerate(csv.DictReader(csv_file), start=2):
            views_by_date[row["date"].strip()] = parse_views(row["global_views"], path, line)

    if not views_by_date:
        raise SystemExit(f"{path.name} has no rows. Add data or remove the file.")

    # Every calendar day from first to last gets an entry, so a date that was
    # never pasted in counts as missing just like a NaN row.
    first = date.fromisoformat(min(views_by_date))
    last = date.fromisoformat(max(views_by_date))
    days = []
    for offset in range((last - first).days + 1):
        day = (first + timedelta(days=offset)).isoformat()
        days.append({"date": day, "views": views_by_date.get(day)})
    return {
        "slug": slug,
        "name": DISPLAY_NAMES.get(slug, slug.replace("_", " ").title()),
        "days": days,
    }


def missing_summary(artist):
    missing = [day["date"] for day in artist["days"] if day["views"] is None]
    if not missing:
        return None
    dates = ", ".join(f"{day:%b} {day.day}" for day in map(date.fromisoformat, missing))
    return f"  {artist['name']}: {len(missing)} missing {'day' if len(missing) == 1 else 'days'} ({dates})"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fragment", type=Path, help="Also write the page without its document wrapper")
    args = parser.parse_args()

    artists = sorted(
        (read_artist(path) for path in CHARTS_DIR.glob("*.csv")),
        key=lambda artist: artist["name"],
    )
    if not artists:
        parser.exit(1, f"No CSV files found in {CHARTS_DIR}.\n")

    page = TEMPLATE.read_text(encoding="utf-8").replace(
        "__ARTIST_DATA__", json.dumps(artists, separators=(",", ":"))
    )
    OUTPUT.write_text(PAGE_START + page + PAGE_END, encoding="utf-8")
    if args.fragment:
        args.fragment.write_text(page, encoding="utf-8")

    names = ", ".join(artist["name"] for artist in artists)
    print(f"Saved {OUTPUT.relative_to(ROOT)} with {len(artists)} artists: {names}")
    gaps = [line for line in map(missing_summary, artists) if line]
    if gaps:
        print("Missing days, left out of the weekly stats:")
        print("\n".join(gaps))


if __name__ == "__main__":
    main()
