"""Build a self-contained SVG from GitHub's public contribution calendar."""

import argparse
import math
import os
import re
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urlencode


class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells = {}
        self.counts = {}
        self.labels = {}
        self.tooltip = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("data-date"):
            day = attrs["data-date"]
            date.fromisoformat(day)
            if attrs.get("id"):
                self.cells[attrs["id"]] = day
            if "data-count" in attrs:
                self.counts[day] = int(attrs["data-count"])
        if tag == "tool-tip":
            self.tooltip = attrs.get("for")
            self.text = []

    def handle_data(self, data):
        if self.tooltip:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self.tooltip:
            label = "".join(self.text).strip()
            match = re.match(r"(No|[\d,]+)\s+contributions?\b", label, re.I)
            if match:
                value = match[1]
                self.labels[self.tooltip] = 0 if value.lower() == "no" else int(value.replace(",", ""))
            self.tooltip = None

    def result(self):
        counts = dict(self.counts)
        for cell, count in self.labels.items():
            if cell in self.cells:
                counts[self.cells[cell]] = count
        return counts


def parse_calendar(html):
    parser = CalendarParser()
    parser.feed(html)
    return parser.result()


def fetch_counts(user, start, end):
    counts = {}
    for year in range(start.year, end.year + 1):
        params = urlencode({
            "from": max(start, date(year, 1, 1)).isoformat(),
            "to": min(end, date(year, 12, 31)).isoformat(),
        })
        url = f"https://github.com/users/{quote(user, safe='')}/contributions?{params}"
        request = urllib.request.Request(url, headers={
            "User-Agent": "GitHub-Profile-Activity-Graph",
            "Accept": "text/html",
            "Accept-Language": "en-US,en;q=0.9",
        })
        with urllib.request.urlopen(request, timeout=30) as response:
            counts.update(parse_calendar(response.read().decode("utf-8")))
    return counts


def select_days(counts, start, end):
    days = []
    for offset in range((end - start).days + 1):
        day = (start + timedelta(days=offset)).isoformat()
        count = counts.get(day)
        if not isinstance(count, int) or count < 0:
            raise ValueError(f"Missing or invalid contribution count for {day}; keeping the existing graph")
        days.append((day, count))
    return days


def build_svg(user, days):
    left, right, top, bottom = 64, 832, 111, 225
    total = sum(count for _, count in days)
    active = sum(count > 0 for _, count in days)
    step = max(1, math.ceil(max(count for _, count in days) / 4))
    ceiling = step * 4
    points = [(left + i * (right - left) / (len(days) - 1),
               bottom - count * (bottom - top) / ceiling) for i, (_, count) in enumerate(days)]
    line = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    area = f"{left},{bottom} {line} {right},{bottom}"
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 300" width="880" height="300" role="img" aria-labelledby="title desc">',
        '<title id="title">Contribution Activity</title>',
        f'<desc id="desc">{escape(user)}: {total} contributions from {days[0][0]} to {days[-1][0]}, as shown on the public GitHub profile. Today is partial.</desc>',
        '<style>text{font-family:ui-monospace,Menlo,Consolas,monospace;fill:#111111}.muted{fill:#666666}</style>',
        '<rect x="16" y="20" width="848" height="270" fill="#111111"/>',
        '<rect x="8" y="12" width="848" height="270" fill="#f4f1ea" stroke="#111111" stroke-width="4"/>',
        '<rect x="34" y="32" width="8" height="22" fill="#0A84FF"/>',
        '<text x="52" y="50" font-size="17" font-weight="700">CONTRIBUTION ACTIVITY</text>',
        f'<text x="832" y="49" text-anchor="end" font-size="12" class="muted">LAST {len(days)} DAYS</text>',
        f'<text x="34" y="78" font-size="13">{total:,} contributions · {active} active days</text>',
        f'<text x="832" y="78" text-anchor="end" font-size="11" class="muted">{days[0][0]} — {days[-1][0]}</text>',
    ]
    for i in range(5):
        value = i * step
        y = bottom - i * (bottom - top) / 4
        parts.append(f'<line x1="{left}" y1="{y}" x2="{right}" y2="{y}" stroke="#111111" stroke-opacity="0.12"/>')
        parts.append(f'<text x="52" y="{y + 4}" text-anchor="end" font-size="11" class="muted">{value}</text>')
    parts.append(f'<polygon points="{area}" fill="#FFD60A" fill-opacity="0.28"/>')
    parts.append(f'<polyline points="{line}" fill="none" stroke="#0A84FF" stroke-width="2.5" stroke-linejoin="round"/>')
    for (day, count), (x, y) in zip(days, points):
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="#FF453A" stroke="#f4f1ea" stroke-width="1"><title>{day}: {count} contributions</title></circle>')
    for i in sorted({round(j * (len(days) - 1) / 6) for j in range(7)}):
        label = date.fromisoformat(days[i][0]).strftime("%m/%d")
        parts.append(f'<text x="{points[i][0]:.2f}" y="246" text-anchor="middle" font-size="11" class="muted">{label}</text>')
    parts.extend([
        '<text x="34" y="269" font-size="10.5" class="muted">Source: GitHub public profile · Today is partial</text>',
        '<text x="832" y="269" text-anchor="end" font-size="10.5" class="muted">Refresh: every 12 hours</text>',
        '</svg>\n',
    ])
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", default=os.environ.get("GH_USER", "xiaohuliming"))
    parser.add_argument("--days", type=int, default=31)
    parser.add_argument("--end-date", type=date.fromisoformat, default=datetime.now(timezone.utc).date())
    parser.add_argument("--calendar-html", type=Path, help="Use a saved GitHub calendar for offline rendering")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "assets/activity-graph.svg")
    args = parser.parse_args()
    if not 2 <= args.days <= 366:
        parser.error("--days must be between 2 and 366")
    start = args.end_date - timedelta(days=args.days - 1)
    counts = parse_calendar(args.calendar_html.read_text()) if args.calendar_html else fetch_counts(args.user, start, args.end_date)
    days = select_days(counts, start, args.end_date)
    svg = build_svg(args.user, days)
    # Only replace the saved graph after fetching and validating every day.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".svg.tmp")
    temporary.write_text(svg, encoding="utf-8")
    temporary.replace(args.output)
    print(f"Saved {args.output}: {len(days)} days, {sum(n for _, n in days)} contributions")


if __name__ == "__main__":
    main()
