"""Render a GitHub contribution calendar as a static SVG, in light and dark.

The hosted services that draw this either went offline (github-readme-activity-graph,
ssr-contributions) or hard-code a light empty-cell colour that glares on GitHub's dark
theme (ghchart), so we draw it here instead. No token needed: the calendar is public
HTML on the profile page.
"""

import datetime as dt
import html.parser
import re
import sys
import urllib.request

CELL = 11          # square size
GAP = 3
PITCH = CELL + GAP
LEFT = 30          # room for the weekday labels
TOP = 20           # room for the month labels

THEMES = {
    "light": {
        "levels": ["#ebedf0", "#bfd6f6", "#8dbdff", "#4b91f1", "#3178c6"],
        "label": "#57606a",
    },
    "dark": {
        "levels": ["#161b22", "#1f3b5c", "#2a5d99", "#3178c6", "#00b8d9"],
        "label": "#8b949e",
    },
}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class DayParser(html.parser.HTMLParser):
    """Collect (date, level) for every cell in the calendar table."""

    def __init__(self):
        super().__init__()
        self.days = []

    def handle_starttag(self, tag, attrs):
        if tag != "td":
            return
        a = dict(attrs)
        if "data-date" not in a or "data-level" not in a:
            return
        self.days.append((dt.date.fromisoformat(a["data-date"]), int(a["data-level"])))


def fetch(user):
    req = urllib.request.Request(
        f"https://github.com/users/{user}/contributions",
        headers={"User-Agent": "contribution-graph", "Accept": "text/html"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read().decode("utf-8", "replace")
    p = DayParser()
    p.feed(body)
    if not p.days:
        raise SystemExit("no contribution cells found; the profile page markup may have changed")
    return sorted(set(p.days))


def render(days, theme):
    t = THEMES[theme]
    # GitHub's calendar runs Sunday-first; anchor on the Sunday of the first week.
    start = days[0][0]
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)

    cells, month_labels, seen_months = [], [], set()
    for date, level in days:
        col = (date - start).days // 7
        row = (date.weekday() + 1) % 7
        x = LEFT + col * PITCH
        y = TOP + row * PITCH
        cells.append(
            f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" '
            f'fill="{t["levels"][level]}"><title>{date.isoformat()}</title></rect>'
        )
        # Label each month above the column holding its first day.
        key = (date.year, date.month)
        if key not in seen_months:
            seen_months.add(key)
            month_labels.append((x, MONTHS[date.month - 1]))

    # The window opens mid-month, so the first label would sit on top of the
    # second one. GitHub drops it too and starts at the first whole month.
    if len(month_labels) > 1 and month_labels[1][0] - month_labels[0][0] < 3 * PITCH:
        month_labels.pop(0)

    cols = max((d[0] - start).days // 7 for d in days) + 1
    width = LEFT + cols * PITCH
    height = TOP + 7 * PITCH

    text = [
        f'<text x="{x}" y="13" fill="{t["label"]}" font-size="10">{name}</text>'
        for x, name in month_labels
    ]
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        y = TOP + row * PITCH + CELL - 1
        text.append(f'<text x="0" y="{y}" fill="{t["label"]}" font-size="10">{name}</text>')

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="-apple-system,BlinkMacSystemFont,'
        f'Segoe UI,Helvetica,Arial,sans-serif">'
        + "".join(text) + "".join(cells) + "</svg>"
    )


def main():
    user, out_dir = sys.argv[1], sys.argv[2]
    days = fetch(user)
    total = sum(1 for _, level in days if level > 0)
    print(f"{len(days)} days, {total} with contributions")
    for theme, name in (("light", "contributions.svg"), ("dark", "contributions-dark.svg")):
        path = f"{out_dir}/{name}"
        with open(path, "w", encoding="utf-8") as f:
            f.write(render(days, theme))
        print("wrote", path)


if __name__ == "__main__":
    main()
