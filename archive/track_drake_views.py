"""Track Drake's YouTube views with the Data API, plus a one-time Kworb backfill.

snapshot: record today's official view totals. Run once a day; daily views are
          the difference between consecutive snapshots.
backfill: save Kworb's recent per-video daily estimates (about 12 days).
"""

import argparse
import csv
import html
import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "drake"
KWORB_URL = "https://kworb.net/youtube"
API_URL = "https://www.googleapis.com/youtube/v3/videos"
BATCH_SIZE = 50
KWORB_DELAY_SECONDS = 1
MIN_KWORB_COVERAGE = 0.9

SNAPSHOTS_CSV = DATA_DIR / "api_snapshots.csv"
DAILY_CSV = DATA_DIR / "api_daily_views.csv"
KWORB_VIDEOS_CSV = DATA_DIR / "kworb_by_video.csv"
KWORB_DAILY_CSV = DATA_DIR / "kworb_daily.csv"


def fetch_text(url, headers=None):
    request = Request(url, headers={"User-Agent": "curl/8.5.0", **(headers or {})})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def fetch_with_retries(url, attempts=3):
    """Retry network failures, but not HTTP errors such as 404 or 429."""
    for attempt in range(1, attempts + 1):
        try:
            return fetch_text(url)
        except HTTPError:
            raise
        except URLError:
            if attempt == attempts:
                raise
            time.sleep(5 * attempt)


def load_api_key():
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "YOUTUBE_API_KEY":
                return value.strip()
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        raise ValueError("Set YOUTUBE_API_KEY in .env.")
    return key


def kworb_videos():
    """Return {video_id: title} for every video Kworb lists for Drake."""
    page = fetch_text(f"{KWORB_URL}/artist/drake.html")
    links = re.findall(r'<a href="\.\./video/([\w-]{11})\.html">(.*?)</a>', page)
    if not links:
        raise ValueError("Found no videos on Kworb's Drake page.")
    return {video_id: html.unescape(title) for video_id, title in links}


def fetch_view_counts(video_ids, api_key):
    rows = []
    for start in range(0, len(video_ids), BATCH_SIZE):
        query = urlencode({
            "part": "snippet,statistics",
            "id": ",".join(video_ids[start:start + BATCH_SIZE]),
            "maxResults": BATCH_SIZE,
        })
        body = fetch_text(f"{API_URL}?{query}", {"x-goog-api-key": api_key})
        for item in json.loads(body)["items"]:
            if "viewCount" in item["statistics"]:
                rows.append({
                    "video_id": item["id"],
                    "title": item["snippet"]["title"],
                    "channel": item["snippet"]["channelTitle"],
                    "views": int(item["statistics"]["viewCount"]),
                })
    return rows


def read_snapshots():
    if not SNAPSHOTS_CSV.exists():
        return []
    with SNAPSHOTS_CSV.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_daily_views(snapshots):
    """Compare consecutive snapshots, using only videos present in both."""
    by_date = defaultdict(dict)
    for row in snapshots:
        by_date[row["date"]][row["video_id"]] = int(row["views"])

    dates = sorted(by_date)
    rows = []
    for previous, current in zip(dates, dates[1:]):
        shared = by_date[previous].keys() & by_date[current].keys()
        rows.append({
            "date": current,
            "days_since_previous": (
                datetime.fromisoformat(current) - datetime.fromisoformat(previous)
            ).days,
            "views_gained": sum(
                by_date[current][video] - by_date[previous][video] for video in shared
            ),
            "videos_compared": len(shared),
        })
    write_csv(
        DAILY_CSV,
        ["date", "days_since_previous", "views_gained", "videos_compared"],
        rows,
    )
    return len(rows)


def snapshot():
    video_ids = list(kworb_videos())
    counts = fetch_view_counts(video_ids, load_api_key())
    today = datetime.now(timezone.utc).date().isoformat()

    # Rerunning on the same day replaces that day's snapshot.
    snapshots = [row for row in read_snapshots() if row["date"] != today]
    snapshots += [{"date": today, **row} for row in counts]
    write_csv(
        SNAPSHOTS_CSV, ["date", "video_id", "title", "channel", "views"], snapshots
    )
    daily_rows = write_daily_views(snapshots)

    total = sum(row["views"] for row in counts)
    print(f"Saved {len(counts)} of {len(video_ids)} videos for {today}: {total:,} views")
    print(f"Daily rows available: {daily_rows}")


def backfill():
    videos = kworb_videos()
    rows = []
    skipped = []
    for video_id, title in videos.items():
        time.sleep(KWORB_DELAY_SECONDS)
        try:
            page = fetch_with_retries(f"{KWORB_URL}/video/{video_id}.html")
        except HTTPError as error:
            if error.code == 429:
                raise
            skipped.append(video_id)
            continue
        except URLError:
            skipped.append(video_id)
            continue
        section = page.partition("Most recent data:")[2].partition("</table>")[0]
        days = re.findall(r"<td>(\d{4}/\d{2}/\d{2})</td><td>([\d,]+)</td>", section)
        if not days:
            skipped.append(video_id)
        rows += [
            {
                "date": day.replace("/", "-"),
                "video_id": video_id,
                "title": title,
                "views": int(count.replace(",", "")),
            }
            for day, count in days
        ]
    if not rows:
        raise ValueError("Found no daily data on Kworb's video pages.")

    write_csv(KWORB_VIDEOS_CSV, ["date", "video_id", "title", "views"], rows)
    totals = defaultdict(lambda: [0, 0])
    for row in rows:
        totals[row["date"]][0] += row["views"]
        totals[row["date"]][1] += 1
    write_csv(
        KWORB_DAILY_CSV,
        ["date", "estimated_views", "videos_reporting"],
        [
            {"date": day, "estimated_views": views, "videos_reporting": videos_seen}
            for day, (views, videos_seen) in sorted(totals.items())
            # Kworb keeps old rows for inactive videos; skip those partial days.
            if videos_seen >= MIN_KWORB_COVERAGE * len(videos)
        ],
    )
    print(f"Saved {len(totals)} days from {len(videos) - len(skipped)} videos "
          f"({len(skipped)} skipped) to {KWORB_DAILY_CSV.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["snapshot", "backfill"])
    args = parser.parse_args()

    try:
        snapshot() if args.command == "snapshot" else backfill()
    except HTTPError as error:
        parser.exit(1, f"Request failed: HTTP {error.code} {error.reason}\n")
    except (URLError, ValueError, KeyError, OSError) as error:
        parser.exit(1, f"Could not update Drake's views: {error}\n")


if __name__ == "__main__":
    main()
