#!/usr/bin/env python3
"""Build profile cards from public GitHub data using only the standard library."""

import json
import os
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen

USER = "NikitaTLN"
ASSETS = Path(__file__).resolve().parents[1] / "assets"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
COLORS = ["#c4b5fd", "#7dd3fc", "#f0abfc", "#a5b4fc", "#f9a8d4", "#94a3b8"]
FONT = "'DejaVu Sans',Arial,sans-serif"
MONO = "'DejaVu Sans Mono',Consolas,monospace"


def api(path, payload=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "NikitaTLN-profile-stats",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    request = Request(
        f"https://api.github.com/{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers=headers,
    )
    with urlopen(request, timeout=30) as response:
        data = json.load(response)
    if isinstance(data, dict) and data.get("errors"):
        raise RuntimeError(f"GitHub GraphQL error: {data['errors']}")
    return data


def text(x, y, value, size=18, color="#b3b2cc", mono=False, weight="400"):
    family = MONO if mono else FONT
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-family="{family}" '
        f'font-size="{size}" font-weight="{weight}">{escape(str(value))}</text>'
    )


def frame(width, height, title, description):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>',
        f'<rect x=".5" y=".5" width="{width-1}" height="{height-1}" '
        'rx="16" fill="#13172b" stroke="#303450"/>',
    ]


def stats_card(stats, date, mobile=False):
    width, height = (600, 450) if mobile else (1200, 280)
    columns = 2 if mobile else 3
    title = "A little activity, in numbers."
    description = "; ".join(f"{value:,} {label}" for label, value, _ in stats)
    svg = frame(width, height, title, description)
    svg += [text(28, 42, title, 25, "#f0f0ff", weight="600")]
    for i, (label, value, period) in enumerate(stats):
        x = 28 + i % columns * ((width - 56) / columns)
        y = 100 + i // columns * (119 if mobile else 77)
        svg += [
            text(x, y, f"{value:,}", 36 if mobile else 32, COLORS[i], weight="700"),
            text(x, y + 26, label, 18),
            text(x, y + 45, period, 12, "#a4a3c1", mono=True),
        ]
    svg += [text(28, height - 20, f"PUBLIC GITHUB DATA / UPDATED {date}", 11, "#a4a3c1", mono=True), "</svg>"]
    return "\n".join(svg) + "\n"


def language_card(languages, date, mobile=False):
    width, height = (600, 430) if mobile else (1200, 300)
    total = sum(languages.values())
    visible = languages.most_common(5)
    remainder = total - sum(value for _, value in visible)
    if remainder:
        visible.append(("Other", remainder))
    description = "Share of code bytes across my public, non-fork repositories."
    svg = frame(width, height, "Languages in my repositories", description)
    svg += [text(28, 42, "Languages in my repositories", 25, "#f0f0ff", weight="600")]
    if not total:
        svg += [text(28, 100, "No public language data yet.")]
    else:
        bar_width = width - 56
        position = 28
        for i, (_, value) in enumerate(visible):
            segment = value / total * bar_width
            svg.append(f'<rect x="{position:.3f}" y="72" width="{segment:.3f}" height="16" fill="{COLORS[i]}"/>')
            position += segment
        for i, (language, value) in enumerate(visible):
            columns = 2 if mobile else 3
            x = 28 + i % columns * ((width - 56) / columns)
            y = 135 + i // columns * (74 if mobile else 58)
            svg += [
                f'<circle cx="{x+5}" cy="{y-6}" r="4" fill="{COLORS[i]}"/>',
                text(x + 19, y, language, 19, "#f0f0ff"),
                text(x + 19, y + 24, f"{value / total:.1%}", 17, COLORS[i], mono=True),
            ]
    svg += [
        text(28, height - 46, "Share of code bytes; public non-fork repos.", 13),
        text(28, height - 20, f"UPDATED {date}", 11, "#a4a3c1", mono=True),
        "</svg>",
    ]
    return "\n".join(svg) + "\n"


def main():
    if not TOKEN:
        raise SystemExit("Set GH_TOKEN or GITHUB_TOKEN to read contribution statistics.")
    profile = api(f"users/{USER}")
    repositories = []
    page = 1
    while True:
        batch = api(f"users/{USER}/repos?type=owner&per_page=100&page={page}")
        repositories.extend(repo for repo in batch if not repo["private"])
        if len(batch) < 100:
            break
        page += 1
    contributions = api("graphql", {"query": """
        query {
          user(login: "NikitaTLN") {
            contributionsCollection {
              totalCommitContributions
              totalPullRequestContributions
              contributionCalendar { totalContributions }
            }
          }
        }
    """})["data"]["user"]["contributionsCollection"]
    stats = [
        ("Public repositories", profile["public_repos"], "all time"),
        ("Stars earned", sum(repo["stargazers_count"] for repo in repositories if not repo["fork"]), "owned non-fork repos"),
        ("Followers", profile["followers"], "right now"),
        ("Contributions", contributions["contributionCalendar"]["totalContributions"], "past year"),
        ("Commit contributions", contributions["totalCommitContributions"], "past year"),
        ("Pull requests", contributions["totalPullRequestContributions"], "past year"),
    ]
    languages = Counter()
    for repo in repositories:
        if not repo["fork"]:
            languages.update(api(f"repos/{USER}/{repo['name']}/languages"))
    date = datetime.now(timezone.utc).date().isoformat()
    ASSETS.mkdir(exist_ok=True)
    for mobile in (False, True):
        suffix = "-mobile" if mobile else ""
        (ASSETS / f"stats{suffix}.svg").write_text(stats_card(stats, date, mobile))
        (ASSETS / f"languages{suffix}.svg").write_text(language_card(languages, date, mobile))
    print(f"Updated four cards from {len(repositories)} public repositories.")


if __name__ == "__main__":
    main()
