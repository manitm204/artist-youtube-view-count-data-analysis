"""Build dashboard/index.html from every CSV in data/charts.

To add an artist, save data/charts/<artist_name>.csv and rerun this script. The
file name becomes the display name, so bad_bunny.csv shows as "Bad Bunny".
"""

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHARTS_DIR = ROOT / "data" / "charts"
TEMPLATE = ROOT / "dashboard" / "template.html"
OUTPUT = ROOT / "dashboard" / "index.html"

# Only needed when title case gets a name wrong, such as {"sza": "SZA"}.
DISPLAY_NAMES = {}

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


def read_artist(path):
    slug = path.stem
    with path.open(newline="", encoding="utf-8") as csv_file:
        days = [
            {"date": row["date"], "views": int(row["global_views"])}
            for row in csv.DictReader(csv_file)
        ]
    days.sort(key=lambda day: day["date"])
    return {
        "slug": slug,
        "name": DISPLAY_NAMES.get(slug, slug.replace("_", " ").title()),
        "days": days,
    }


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


if __name__ == "__main__":
    main()
