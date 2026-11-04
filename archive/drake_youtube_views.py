"""Save Drake's latest 28 published daily Global view counts as CSV."""

import argparse
import csv
from datetime import date, datetime, timedelta
from pathlib import Path

from playwright.sync_api import Error, sync_playwright

ARTIST_URL = "https://charts.youtube.com/artist/%2Fm%2F05mt_q"
DAYS = 28


def fetch_views(end_date, chromium_path):
    url = ARTIST_URL
    if end_date:
        url += f"?date_end={end_date}T00%3A00%3A00Z"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=chromium_path)
        page = browser.new_page(locale="en-US")
        page.goto(url, wait_until="domcontentloaded")
        page.get_by_text("Last 28 days", exact=True).wait_for()
        page.get_by_text("Global ·", exact=False).first.wait_for()

        # The chart exposes its exact counts in an off-screen HTML table.
        table = page.locator("table").filter(
            has=page.get_by_text("Views", exact=True)
        ).filter(has=page.get_by_text("Date", exact=True)).first
        table.locator("tr").nth(DAYS).wait_for(state="attached")
        rows = table.locator("tr").evaluate_all(
            "(rows) => rows.slice(1).map(row => "
            "Array.from(row.cells, cell => cell.textContent.trim()))"
        )
        browser.close()

    views = sorted(
        (datetime.strptime(day, "%b %d, %Y").date(), int(count.replace(",", "")))
        for day, count in rows
    )
    if len(views) != DAYS or any(
        day != views[0][0] + timedelta(days=index)
        for index, (day, _) in enumerate(views)
    ):
        raise ValueError("Expected 28 consecutive daily counts from YouTube Charts.")
    if end_date and views[-1][0] != end_date:
        raise ValueError(f"Requested data through {end_date}, got {views[-1][0]}.")
    return views


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--end-date", type=date.fromisoformat, metavar="YYYY-MM-DD")
    parser.add_argument("--output", type=Path, default=Path("drake_youtube_views.csv"))
    parser.add_argument("--chromium-path", help="Optional path to an installed Chromium")
    args = parser.parse_args()

    try:
        views = fetch_views(args.end_date, args.chromium_path)
        with args.output.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(["date", "global_views"])
            writer.writerows(views)
    except (Error, ValueError, OSError) as error:
        parser.exit(1, f"Could not export Drake's daily views: {error}\n")

    print(f"Saved {len(views)} days ({views[0][0]} to {views[-1][0]}) to {args.output}")


if __name__ == "__main__":
    main()
