"""
render.py
---------
Builds the combined "generated network art + neofetch stats panel" SVG in both
light_mode.svg and dark_mode.svg flavors.

This module only knows how to draw. All the *numbers* (repos, stars,
commits, lines of code) are computed in today.py and passed in as a
plain dict, so this file never needs to touch the GitHub API.
"""

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Static bio fields — edit these whenever your info changes.
# Everything under GitHub Stats is computed automatically by today.py instead.
# ---------------------------------------------------------------------------
BIO = {
    "user_at_host": "kunal@admin",
    "OS": "Windows 11, Android 16, Ubuntu Linux",
    "Host": "Worley India Private Limited",
    "Kernel": "Data Scientist / AI Engineer",
    "IDE": "VSCode 1.141.0",
    "Languages.Programming": "Python, Shell Script, PowerShell",
    "Languages.Computer": "HTML, CSS, YAML, Markdown",
    "Languages.Real": "English",
    "Hobbies.Software": "Android rooting, custom ROMs, rclone",
    "Hobbies.Hardware": "GPU overclocking",
    "Email": "kunal1520018@gmail.com",
    "LinkedIn": "kunal152001",
    "Medium": "@kunal1520018",
    "Discord": "BillionGarage",
}

# Work-experience start date used to compute a live "Uptime" field.
# 2022-07-12 -> 4y 0m as of 2026-07-12. Adjust the day/month if you want
# a more exact start date; it will keep counting up on every Action run.
WORK_START_DATE = (2022, 7, 12)

FONT_STACK = (
    "'JetBrains Mono','IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
)

COLORS = {
    "light": {
        "bg": "#ffffff",
        "label": "#8a4b08",   # amber/brown labels
        "value": "#1a1a1a",
        "header": "#0969da",
        "dim": "#6e7781",
        "border": "#d0d7de",
    },
    "dark": {
        "bg": "#0d1117",
        "label": "#e3b341",   # amber
        "value": "#e6edf3",
        "header": "#39d98a",
        "dim": "#7d8590",
        "border": "#30363d",
    },
}

ART_COLORS = {
    "light": {"edge": "#d0d7de", "node": "#0969da", "pulse": "#1a7f37", "accent": "#8250df", "dim": "#6e7781"},
    "dark": {"edge": "#30363d", "node": "#58a6ff", "pulse": "#39d98a", "accent": "#bc8cff", "dim": "#7d8590"},
}


def _uptime_string():
    from datetime import date
    y0, m0, d0 = WORK_START_DATE
    start = date(y0, m0, d0)
    today = date.today()
    years = today.year - start.year
    months = today.month - start.month
    days = today.day - start.day
    if days < 0:
        months -= 1
        # roughly 30 days per "borrowed" month, good enough for a bio line
        days += 30
    if months < 0:
        years -= 1
        months += 12
    return f"{years} years, {months} months, {days} days"


def _dotted_line(label, value, width=44):
    """neofetch-style 'Label: ..... value' line, dot-padded to width."""
    prefix = f"{label}:"
    dots_needed = max(1, width - len(prefix))
    return f"{prefix} {'.' * dots_needed} {value}"


def _escape(s):
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _build_art(mode, w, h):
    """Animated 'neural network' hero graphic (no portrait): layered nodes,
    signal pulses flowing along the edges, and a name/title block beneath.
    Returns (css, svg_fragment) drawn in a w x h box at the origin."""
    pal = ART_COLORS[mode]
    layers = [4, 7, 7, 4, 2]
    net_h = h - 150
    margin_x = 40
    xs = [margin_x + i * (w - 2 * margin_x) / (len(layers) - 1) for i in range(len(layers))]

    nodes = []  # per layer: list of (x, y)
    for x, n in zip(xs, layers):
        gap = net_h / (n + 1)
        nodes.append([(x, gap * (j + 1) + 10) for j in range(n)])

    edges, k = [], 0
    for a, b in zip(nodes, nodes[1:]):
        for i, (x1, y1) in enumerate(a):
            for j, (x2, y2) in enumerate(b):
                # deterministic pseudo-random subset so the graph feels organic
                if (i * 7 + j * 13 + k) % 3 == 0:
                    continue
                k += 1
                edges.append((x1, y1, x2, y2, (i * 5 + j * 3 + k) % 9))

    parts = []
    for x1, y1, x2, y2, d in edges:
        parts.append(f'<line class="edge" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
        parts.append(
            f'<line class="flow" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'style="animation-delay:{d * 0.45:.2f}s"/>'
        )
    for li, layer in enumerate(nodes):
        for ni, (x, y) in enumerate(layer):
            cls = "node-out" if li == len(nodes) - 1 else ("node-in" if li == 0 else "node")
            delay = (li * 0.5 + ni * 0.23) % 3
            parts.append(f'<circle class="halo {cls}" cx="{x:.1f}" cy="{y:.1f}" r="11" style="animation-delay:{delay:.2f}s"/>')
            parts.append(f'<circle class="{cls}" cx="{x:.1f}" cy="{y:.1f}" r="5.5"/>')

    ty = net_h + 62
    labels = "".join(
        f'<text class="cap" x="{x:.0f}" y="{net_h + 22:.0f}" text-anchor="middle">{t}</text>'
        for x, t in zip((xs[0], xs[2], xs[-1]), ("data", "models", "impact"))
    )
    title = (
        f'<text class="big" x="{w / 2:.0f}" y="{ty + 22:.0f}" text-anchor="middle">KUNAL</text>'
        f'<text class="sub" x="{w / 2:.0f}" y="{ty + 54:.0f}" text-anchor="middle">'
        f'DATA SCIENTIST  ·  GEN AI  ·  AUTOMATION</text>'
        f'<text class="cur" x="{w / 2:.0f}" y="{ty + 82:.0f}" text-anchor="middle">&gt; building intelligent systems_</text>'
    )

    css = f"""
    .edge {{ stroke: {pal['edge']}; stroke-width: 1; }}
    .flow {{ stroke: {pal['pulse']}; stroke-width: 1.8; stroke-linecap: round;
            stroke-dasharray: 6 90; stroke-dashoffset: 96; animation: flow 4s linear infinite; }}
    .node {{ fill: {pal['node']}; }}
    .node-in {{ fill: {pal['pulse']}; }}
    .node-out {{ fill: {pal['accent']}; }}
    .halo {{ opacity: 0; animation: pulse 3s ease-in-out infinite; }}
    .halo.node {{ fill: {pal['node']}; }}
    .cap {{ fill: {pal['dim']}; font-size: 13px; letter-spacing: 3px; text-transform: uppercase; }}
    .big {{ fill: {pal['accent']}; font-size: 54px; font-weight: 800; letter-spacing: 14px; }}
    .sub {{ fill: {pal['dim']}; font-size: 13px; letter-spacing: 2px; }}
    .cur {{ fill: {pal['pulse']}; font-size: 15px; animation: blink 2.4s steps(1) infinite; }}
    @keyframes flow {{ to {{ stroke-dashoffset: 0; }} }}
    @keyframes pulse {{ 0%,100% {{ opacity: 0; transform: scale(.6); }} 50% {{ opacity: .28; transform: scale(1.5); }} }}
    @keyframes blink {{ 50% {{ opacity: .35; }} }}
    .halo {{ transform-box: fill-box; transform-origin: center; }}
    """
    return css, "".join(parts) + labels + title


def build_stats_lines(stats):
    """stats is a dict produced by today.py, e.g.:
    {
      "repos_owned": 95, "repos_contributed": 133,
      "stars": 342, "commits": 2116, "followers": 196,
      "loc_total": 446276, "loc_added": 523178, "loc_deleted": 76902,
    }
    """
    repo_val = f"{stats['repos_owned']} {{Contributed: {stats['repos_contributed']}}} | Stars: {stats['stars']}"
    commit_val = f"{stats['commits']:,} | Followers: {stats['followers']}"
    loc_val = f"{stats['loc_total']:,} ({stats['loc_added']:,}++, {stats['loc_deleted']:,}--)"
    return [
        _dotted_line("Repos", repo_val),
        _dotted_line("Commits", commit_val),
        _dotted_line("Lines of Code on GitHub", loc_val),
    ]


def build_combined_svg(mode, stats):
    assert mode in ("light", "dark")
    palette = COLORS[mode]

    FONT_SIZE = 18
    LINE_H = 26
    PAD = 18

    lines = []
    lines.append((BIO["user_at_host"], "header"))
    lines.append(("-" * 34, "dim"))
    lines.append((_dotted_line("OS", BIO["OS"]), "kv"))
    lines.append((_dotted_line("Uptime", _uptime_string()), "kv"))
    lines.append((_dotted_line("Host", BIO["Host"]), "kv"))
    lines.append((_dotted_line("Kernel", BIO["Kernel"]), "kv"))
    lines.append((_dotted_line("IDE", BIO["IDE"]), "kv"))
    lines.append(("", "blank"))
    lines.append((_dotted_line("Languages.Programming", BIO["Languages.Programming"]), "kv"))
    lines.append((_dotted_line("Languages.Computer", BIO["Languages.Computer"]), "kv"))
    lines.append((_dotted_line("Languages.Real", BIO["Languages.Real"]), "kv"))
    lines.append(("", "blank"))
    lines.append((_dotted_line("Hobbies.Software", BIO["Hobbies.Software"]), "kv"))
    lines.append((_dotted_line("Hobbies.Hardware", BIO["Hobbies.Hardware"]), "kv"))
    lines.append(("", "blank"))
    lines.append(("- Contact " + "-" * 24, "dim"))
    lines.append((_dotted_line("Email", BIO["Email"]), "kv"))
    lines.append((_dotted_line("LinkedIn", BIO["LinkedIn"]), "kv"))
    lines.append((_dotted_line("Medium", BIO["Medium"]), "kv"))
    lines.append((_dotted_line("Discord", BIO["Discord"]), "kv"))
    lines.append(("", "blank"))
    lines.append(("- GitHub Stats " + "-" * 19, "dim"))
    for l in build_stats_lines(stats):
        lines.append((l, "kv"))

    panel_height = PAD * 2 + len(lines) * LINE_H

    # Left-to-right: generated art gets a fixed column; text panel fills the rest.
    art_col_w = 650
    art_col_h = panel_height - PAD * 2
    art_css, art_body = _build_art(mode, art_col_w, art_col_h)

    PANEL_X = art_col_w + PAD * 2
    total_height = panel_height

    # Text panel width from the longest line.
    char_w = FONT_SIZE * 0.65
    longest_text = max(len(t[0]) for t in lines)
    text_panel_w = max(680, int(longest_text * char_w) + 120)
    total_width = PANEL_X + text_panel_w

    def render_kv_line(text, y):
        if ":" in text:
            label, rest = text.split(":", 1)
            m = re.match(r"([\s.]*)(.*)", rest)
            dots, value = m.group(1), m.group(2)
            return (
                f'<tspan x="{PANEL_X}" y="{y:.2f}">'
                f'<tspan class="lbl">{_escape(label)}:</tspan>'
                f'<tspan class="dim">{_escape(dots)}</tspan>'
                f'<tspan class="val">{_escape(value)}</tspan>'
                f"</tspan>"
            )
        return f'<tspan x="{PANEL_X}" y="{y:.2f}" class="val">{_escape(text)}</tspan>'

    text_tspans = []
    y = PAD + FONT_SIZE
    for text, kind in lines:
        if kind == "header":
            text_tspans.append(
                f'<tspan x="{PANEL_X}" y="{y:.2f}" class="hdr">{_escape(text)}</tspan>'
            )
        elif kind == "dim":
            text_tspans.append(
                f'<tspan x="{PANEL_X}" y="{y:.2f}" class="dim">{_escape(text)}</tspan>'
            )
        elif kind == "blank":
            pass
        else:
            text_tspans.append(render_kv_line(text, y))
        y += LINE_H

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{total_width:.0f}" height="{total_height:.0f}" viewBox="0 0 {total_width:.0f} {total_height:.0f}" role="img" aria-label="{_escape(BIO['user_at_host'])} github profile card">
  <style>
    .bgrect {{ fill: {palette['bg']}; }}
    .hdr {{ fill: {palette['header']}; font-weight: 600; }}
    .lbl {{ fill: {palette['label']}; }}
    .val {{ fill: {palette['value']}; }}
    .dim {{ fill: {palette['dim']}; }}
    text {{ font-family: {FONT_STACK}; }}{art_css}
  </style>
  <rect class="bgrect" x="0" y="0" width="{total_width:.0f}" height="{total_height:.0f}" rx="10"/>
  <g transform="translate({PAD},{PAD})">
    {art_body}
  </g>
  <text xml:space="preserve" font-size="{FONT_SIZE}">
    {''.join(text_tspans)}
  </text>
</svg>'''
    return svg


# ---------------------------------------------------------------------------
# GitHub Trophies — a self-contained reimplementation of the retired
# github-profile-trophy service, so the README never depends on a third party.
# today.py supplies the raw metrics; this module knows the rank thresholds.
# ---------------------------------------------------------------------------

# Highest-first display order (matches the upstream RANK_ORDER enum).
RANK_DISPLAY_ORDER = ["SECRET", "SSS", "SS", "S", "AAA", "AA", "A", "B", "C", "?"]

# Rank badge colours, keyed by the first character of the rank (or "SECRET"/"?").
RANK_COLORS = {
    "light": {
        "SECRET": "#8250df",
        "S": "#b58900",
        "A": "#1a7f37",
        "B": "#0969da",
        "C": "#6e7781",
        "?": "#6e7781",
    },
    "dark": {
        "SECRET": "#bc8cff",
        "S": "#e3b341",
        "A": "#39d98a",
        "B": "#58a6ff",
        "C": "#7d8590",
        "?": "#7d8590",
    },
}

# The seven always-visible trophies. Each is (title, metric key, rank
# conditions). Conditions are listed highest-first: [(rank, threshold,
# message), ...]. Thresholds/messages are copied from the upstream project.
_BASE_TROPHIES = [
    ("Stars", "stars", [
        ("SSS", 2000, "Super Stargazer"), ("SS", 700, "High Stargazer"),
        ("S", 200, "Stargazer"), ("AAA", 100, "Super Star"),
        ("AA", 50, "High Star"), ("A", 30, "You are a Star"),
        ("B", 10, "Middle Star"), ("C", 1, "First Star"),
    ]),
    ("Commits", "commits", [
        ("SSS", 4000, "God Committer"), ("SS", 2000, "Deep Committer"),
        ("S", 1000, "Super Committer"), ("AAA", 500, "Ultra Committer"),
        ("AA", 200, "Hyper Committer"), ("A", 100, "High Committer"),
        ("B", 10, "Middle Committer"), ("C", 1, "First Commit"),
    ]),
    ("Followers", "followers", [
        ("SSS", 1000, "Super Celebrity"), ("SS", 400, "Ultra Celebrity"),
        ("S", 200, "Hyper Celebrity"), ("AAA", 100, "Famous User"),
        ("AA", 50, "Active User"), ("A", 20, "Dynamic User"),
        ("B", 10, "Many Friends"), ("C", 1, "First Friend"),
    ]),
    ("Issues", "issues", [
        ("SSS", 1000, "God Issuer"), ("SS", 500, "Deep Issuer"),
        ("S", 200, "Super Issuer"), ("AAA", 100, "Ultra Issuer"),
        ("AA", 50, "Hyper Issuer"), ("A", 20, "High Issuer"),
        ("B", 10, "Middle Issuer"), ("C", 1, "First Issue"),
    ]),
    ("PullRequest", "pull_requests", [
        ("SSS", 1000, "God Puller"), ("SS", 500, "Deep Puller"),
        ("S", 200, "Super Puller"), ("AAA", 100, "Ultra Puller"),
        ("AA", 50, "Hyper Puller"), ("A", 20, "High Puller"),
        ("B", 10, "Middle Puller"), ("C", 1, "First Pull"),
    ]),
    ("Repositories", "repositories", [
        ("SSS", 50, "God Repo Creator"), ("SS", 45, "Deep Repo Creator"),
        ("S", 40, "Super Repo Creator"), ("AAA", 35, "Ultra Repo Creator"),
        ("AA", 30, "Hyper Repo Creator"), ("A", 20, "High Repo Creator"),
        ("B", 10, "Middle Repo Creator"), ("C", 1, "First Repository"),
    ]),
    ("Reviews", "reviews", [
        ("SSS", 70, "God Reviewer"), ("SS", 57, "Deep Reviewer"),
        ("S", 45, "Super Reviewer"), ("AAA", 30, "Ultra Reviewer"),
        ("AA", 20, "Hyper Reviewer"), ("A", 8, "Active Reviewer"),
        ("B", 3, "Intermediate Reviewer"), ("C", 1, "New Reviewer"),
    ]),
]

# "Experience" is not hidden, but the upstream project groups it with the
# secret trophies. Its metric is account age in hundreds-of-days units.
_EXPERIENCE_CONDITIONS = [
    ("SSS", 70, "Seasoned Veteran"), ("SS", 55, "Grandmaster"),
    ("S", 40, "Master Dev"), ("AAA", 28, "Expert Dev"),
    ("AA", 18, "Experienced Dev"), ("A", 11, "Intermediate Dev"),
    ("B", 6, "Junior Dev"), ("C", 2, "Newbie"),
]


def _rank_for(score, conditions):
    """Return (rank, message) for the first (highest) condition the score meets."""
    for rank, threshold, message in conditions:
        if score >= threshold:
            return rank, message
    return "?", "Unknown"


def _make_trophy(title, score, conditions, hidden=False, label=None):
    rank, message = _rank_for(score, conditions)
    return {
        "title": title, "score": score, "rank": rank, "message": message,
        "hidden": hidden, "count_label": label,
    }


def _account_age_stats(created_at_iso):
    from datetime import date, datetime
    created = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00")).date()
    today = date.today()
    total_days = (today - created).days
    years = today.year - created.year - ((today.month, today.day) < (created.month, created.day))
    return {
        "duration_years": years,
        "duration_days": total_days // 100,  # upstream uses floor(days / 100)
        "ancient": 1 if created.year <= 2010 else 0,
        "og": 1 if created.year <= 2008 else 0,
        "joined2020": 1 if created.year == 2020 else 0,
    }


def _build_trophy_list(ts):
    trophies = [_make_trophy(title, ts[key], conds) for title, key, conds in _BASE_TROPHIES]

    # AllSuperRank: every base trophy (Stars..Reviews) is an S-rank.
    all_s = 1 if all(t["rank"].startswith("S") for t in trophies) else 0

    trophies.append(_make_trophy("Experience", ts["duration_days"], _EXPERIENCE_CONDITIONS))

    secret = [
        ("AllSuperRank", all_s, [("SECRET", 1, "S Rank Hacker")], "All S Rank"),
        ("MultiLanguage", ts["languages"], [("SECRET", 10, "Rainbow Lang User")], None),
        ("LongTimeUser", ts["duration_years"], [("SECRET", 10, "Village Elder")], None),
        ("AncientUser", ts["ancient"], [("SECRET", 1, "Ancient User")], "Before 2010"),
        ("OGUser", ts["og"], [("SECRET", 1, "OG User")], "Joined 2008"),
        ("Joined2020", ts["joined2020"], [("SECRET", 1, "Everything started...")], "Joined 2020"),
        ("Organizations", ts["organizations"], [("SECRET", 3, "Jack of all Trades")], None),
    ]
    for title, score, conds, label in secret:
        trophies.append(_make_trophy(title, score, conds, hidden=True, label=label))
    return trophies


def _trophy_card(t, ox, oy, panel, rank_colors):
    cx = ox + panel / 2
    first = "SECRET" if t["rank"] == "SECRET" else t["rank"][0]
    color = rank_colors.get(first, rank_colors["?"])
    letter = "★" if t["rank"] == "SECRET" else t["rank"]
    title = _escape(t["title"])
    message = _escape(t["message"])
    count = _escape(t["count_label"] if t["count_label"] else f"{t['score']:,}")
    return (
        f'<rect class="card" x="{ox + 0.5:.1f}" y="{oy + 0.5:.1f}" '
        f'width="{panel - 1}" height="{panel - 1}" rx="4.5"/>'
        f'<text class="ttl" x="{cx:.1f}" y="{oy + 21:.1f}">{title}</text>'
        f'<circle cx="{cx:.1f}" cy="{oy + 53:.1f}" r="17" fill="none" '
        f'stroke="{color}" stroke-width="1.5"/>'
        f'<text class="rkg" x="{cx:.1f}" y="{oy + 59:.1f}" fill="{color}">{letter}</text>'
        f'<text class="msg" x="{cx:.1f}" y="{oy + 89:.1f}">{message}</text>'
        f'<text class="cnt" x="{cx:.1f}" y="{oy + 101:.1f}">{count}</text>'
    )


def build_trophies_svg(mode, trophy_stats):
    assert mode in ("light", "dark")
    palette = COLORS[mode]
    rank_colors = RANK_COLORS[mode]

    ts = dict(trophy_stats)
    ts.update(_account_age_stats(ts.get("created_at", "")))

    trophies = _build_trophy_list(ts)
    # Hidden trophies only surface once they unlock (reach their SECRET rank).
    trophies = [t for t in trophies if (not t["hidden"]) or t["rank"] != "?"]
    trophies.sort(key=lambda t: RANK_DISPLAY_ORDER.index(t["rank"]))

    PANEL, MARGIN, COLS = 110, 4, 8
    n = max(1, len(trophies))
    cols = min(COLS, n)
    rows = (n + cols - 1) // cols
    width = PANEL * cols + MARGIN * (cols - 1)
    height = PANEL * rows + MARGIN * (rows - 1)

    cards = []
    for i, t in enumerate(trophies):
        ox = (PANEL + MARGIN) * (i % cols)
        oy = (PANEL + MARGIN) * (i // cols)
        cards.append(_trophy_card(t, ox, oy, PANEL, rank_colors))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="GitHub trophies">
  <style>
    .card {{ fill: {palette['bg']}; stroke: {palette['border']}; }}
    .ttl {{ fill: {palette['value']}; font-size: 12px; font-weight: 700; }}
    .msg {{ fill: {palette['dim']}; font-size: 9px; }}
    .cnt {{ fill: {palette['value']}; font-size: 10px; font-weight: 700; }}
    .rkg {{ font-size: 15px; font-weight: 800; }}
    text {{ font-family: {FONT_STACK}; text-anchor: middle; }}
  </style>
  {''.join(cards)}
</svg>'''


# ---------------------------------------------------------------------------
# GitHub streak card + top-languages bar chart — self-hosted replacements for
# the retired github-readme-streak-stats / github-readme-stats services.
# ---------------------------------------------------------------------------

# Canonical GitHub language colours (subset), plus a neutral fallback.
LANG_COLORS = {
    "Python": "#3572A5",
    "Jupyter Notebook": "#DA5B0B",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "SCSS": "#c6538c",
    "Shell": "#89e051",
    "Dockerfile": "#384d54",
    "TeX": "#3D6117",
    "PLpgSQL": "#336790",
    "Makefile": "#427819",
    "Mako": "#7e858d",
    "XSLT": "#EB8CEB",
    "Markdown": "#083fa1",
    "_default": "#8b949e",
}


def _streak_svg_style(palette):
    return (
        f".bgrect {{ fill: {palette['bg']}; }} "
        f".hdr {{ fill: {palette['header']}; font-weight: 600; }} "
        f".val {{ fill: {palette['value']}; }} "
        f".dim {{ fill: {palette['dim']}; }} "
        f"text {{ font-family: {FONT_STACK}; }}"
    )


def build_streak_svg(mode, streak):
    palette = COLORS[mode]
    W, H = 520, 130
    blocks = [
        ("Total Contributions", f"{streak['total']:,}"),
        ("Current Streak", f"{streak['current']} day{'s' if streak['current'] != 1 else ''}"),
        ("Longest Streak", f"{streak['longest']} day{'s' if streak['longest'] != 1 else ''}"),
    ]
    xs = (130, 260, 390)
    parts = [
        f'<rect class="bgrect" x="0" y="0" width="{W}" height="{H}" rx="10"/>',
        f'<text x="18" y="34" class="hdr" font-size="16">🔥 GitHub Streak</text>',
    ]
    for (label, value), cx in zip(blocks, xs):
        parts.append(
            f'<text x="{cx}" y="78" text-anchor="middle" class="val" '
            f'font-size="26" font-weight="700">{value}</text>'
        )
        parts.append(
            f'<text x="{cx}" y="100" text-anchor="middle" class="dim" '
            f'font-size="11">{label}</text>'
        )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub streak">
  <style>{_streak_svg_style(palette)}</style>
  {''.join(parts)}
</svg>'''


def build_top_langs_svg(mode, langs):
    palette = COLORS[mode]
    W = 460
    NAME_X, BAR_X, BAR_W, BAR_H, PCT_X, ROW_H, TOP_Y = 16, 158, 210, 12, 444, 30, 46
    n = len(langs)
    H = 26 + ROW_H * n + 12
    max_pct = max((l["percent"] for l in langs), default=1) or 1
    parts = [
        f'<rect class="bgrect" x="0" y="0" width="{W}" height="{H}" rx="10"/>',
        f'<text x="16" y="26" class="hdr" font-size="16">Top Languages</text>',
    ]
    for i, l in enumerate(langs):
        name = l["name"]
        if len(name) > 16:
            name = name[:15] + "…"
        color = LANG_COLORS.get(l["name"], LANG_COLORS["_default"])
        bar_w = max(2, round(BAR_W * l["percent"] / max_pct))
        y_bar = TOP_Y - 12 + i * ROW_H
        y_txt = TOP_Y + i * ROW_H
        parts.append(
            f'<text x="{NAME_X}" y="{y_txt}" class="val" font-size="13">{_escape(name)}</text>'
        )
        parts.append(
            f'<rect x="{BAR_X}" y="{y_bar}" width="{bar_w}" height="{BAR_H}" rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{PCT_X}" y="{y_txt}" text-anchor="end" class="dim" '
            f'font-size="12">{l["percent"]:.1f}%</text>'
        )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Top languages">
  <style>{_streak_svg_style(palette)}</style>
  {''.join(parts)}
</svg>'''


# ---------------------------------------------------------------------------
# README glow-up: animated header banner, daily dev quote, project cards and a
# contribution heatmap. All self-hosted, so the README depends on no
# third-party image service.
# ---------------------------------------------------------------------------

HEADER_LINES = [
    "Hi 👋 I am Kunal",
    "Data Scientist",
    "Gen AI Developer",
    "Automation Enthusiast",
    "Building Intelligent Systems",
    "Crafting AI Pipelines",
    "Lover of Clean Code",
]

HEADER_COLORS = {
    "light": {"bg1": "#dbeafe", "bg2": "#ede9fe", "w1": "#0969da", "w2": "#8250df", "w3": "#1a7f37",
              "title": "#1a1a1a", "sub": "#57606a"},
    "dark": {"bg1": "#0d1117", "bg2": "#1e1b4b", "w1": "#58a6ff", "w2": "#bc8cff", "w3": "#39d98a",
             "title": "#e6edf3", "sub": "#9da7b3"},
}


def _wave_path(w, h, amp, phase, periods=2):
    """Closed sine-wave path two canvas-widths long so it can scroll seamlessly."""
    import math
    pts = []
    steps = 80
    total_w = w * 2
    for i in range(steps + 1):
        x = total_w * i / steps
        y = h + amp * math.sin(2 * math.pi * periods * x / total_w * 2 + phase)
        pts.append(f"{x:.1f},{y:.1f}")
    return f"M0,{h * 3} L" + " L".join(pts) + f" L{total_w},{h * 3} Z"


def build_header_svg(mode):
    """Animated banner: scrolling gradient waves + rotating tagline."""
    assert mode in ("light", "dark")
    c = HEADER_COLORS[mode]
    W, H = 1188, 240
    per = 3.2                      # seconds each tagline stays up
    total = per * len(HEADER_LINES)
    frac = per / total * 100

    lines = []
    for i, text in enumerate(HEADER_LINES):
        lines.append(
            f'<text class="tag" x="{W / 2:.0f}" y="168" text-anchor="middle" '
            f'style="animation-delay:{i * per:.1f}s">{_escape(text)}</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Kunal — Data Scientist, Gen AI Developer">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{c['bg1']}"/><stop offset="1" stop-color="{c['bg2']}"/>
    </linearGradient>
    <clipPath id="clip"><rect width="{W}" height="{H}" rx="14"/></clipPath>
  </defs>
  <style>
    text {{ font-family: {FONT_STACK}; }}
    .name {{ fill: {c['title']}; font-size: 52px; font-weight: 800; letter-spacing: 6px; }}
    .tag {{ fill: {c['sub']}; font-size: 24px; opacity: 0; animation: tag {total:.1f}s linear infinite; }}
    .w1 {{ animation: scroll 16s linear infinite; }}
    .w2 {{ animation: scroll 24s linear infinite reverse; }}
    .w3 {{ animation: scroll 34s linear infinite; }}
    .cur {{ fill: {c['w3']}; font-size: 24px; animation: blink 1s steps(1) infinite; }}
    @keyframes scroll {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-{W}px); }} }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
    @keyframes tag {{
      0% {{ opacity: 0; transform: translateY(10px); }}
      3% {{ opacity: 1; transform: translateY(0); }}
      {frac - 3:.2f}% {{ opacity: 1; transform: translateY(0); }}
      {frac:.2f}% {{ opacity: 0; transform: translateY(-10px); }}
      100% {{ opacity: 0; }}
    }}
  </style>
  <g clip-path="url(#clip)">
    <rect width="{W}" height="{H}" fill="url(#bg)"/>
    <path class="w3" d="{_wave_path(W, 200, 14, 2.0)}" fill="{c['w3']}" opacity="0.18"/>
    <path class="w2" d="{_wave_path(W, 210, 18, 1.0)}" fill="{c['w2']}" opacity="0.22"/>
    <path class="w1" d="{_wave_path(W, 220, 16, 0)}" fill="{c['w1']}" opacity="0.28"/>
    <text class="name" x="{W / 2:.0f}" y="100" text-anchor="middle">KUNAL</text>
    {''.join(lines)}
  </g>
</svg>'''


# Real, correctly attributed quotes; one is picked per day.
QUOTES = [
    ("Talk is cheap. Show me the code.", "Linus Torvalds"),
    ("Programs must be written for people to read, and only incidentally for machines to execute.", "Harold Abelson"),
    ("Premature optimization is the root of all evil.", "Donald Knuth"),
    ("Simplicity is prerequisite for reliability.", "Edsger W. Dijkstra"),
    ("Make it work, make it right, make it fast.", "Kent Beck"),
    ("First, solve the problem. Then, write the code.", "John Johnson"),
    ("Any fool can write code that a computer can understand. Good programmers write code that humans can understand.", "Martin Fowler"),
    ("The best way to predict the future is to invent it.", "Alan Kay"),
    ("All models are wrong, but some are useful.", "George E. P. Box"),
    ("Code is like humor. When you have to explain it, it is bad.", "Cory House"),
    ("Before software can be reusable it first has to be usable.", "Ralph Johnson"),
    ("Debugging is twice as hard as writing the code in the first place.", "Brian Kernighan"),
]


def _wrap(text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def build_quote_svg(mode, day=None):
    from datetime import date
    palette = COLORS[mode]
    art = ART_COLORS[mode]
    day = day or date.today()
    quote, author = QUOTES[day.toordinal() % len(QUOTES)]
    lines = _wrap(quote, 62)
    W = 720
    H = 70 + 28 * len(lines) + 44
    body = [
        f'<text x="26" y="62" class="mark">“</text>',
    ]
    for i, l in enumerate(lines):
        body.append(f'<text x="60" y="{78 + i * 28}" class="q">{_escape(l)}</text>')
    body.append(f'<text x="{W - 26}" y="{H - 22}" text-anchor="end" class="by">— {_escape(author)}</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Dev quote of the day">
  <style>
    .bgrect {{ fill: {palette['bg']}; stroke: {palette['border']}; }}
    .bar {{ fill: {art['accent']}; }}
    .mark {{ fill: {art['accent']}; font-size: 54px; font-weight: 800; }}
    .q {{ fill: {palette['value']}; font-size: 18px; font-style: italic; }}
    .by {{ fill: {palette['dim']}; font-size: 14px; }}
    .hd {{ fill: {palette['dim']}; font-size: 11px; letter-spacing: 3px; }}
    text {{ font-family: {FONT_STACK}; }}
  </style>
  <rect class="bgrect" x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10"/>
  <rect class="bar" x="0" y="14" width="5" height="{H - 28}" rx="2"/>
  <text x="{W - 26}" y="26" text-anchor="end" class="hd">DEV QUOTE OF THE DAY</text>
  {''.join(body)}
</svg>'''


def _wrap_ellipsis(text, width, max_lines):
    lines = _wrap(text, width)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: width - 1].rstrip() + "…"
    return lines


def build_project_svg(mode, repo):
    """One project card. repo: {name, description, language, stars, forks}."""
    palette = COLORS[mode]
    art = ART_COLORS[mode]
    W, H = 480, 140
    desc = _wrap_ellipsis(repo.get("description") or "No description yet.", 54, 2)
    lang = repo.get("language") or ""
    color = LANG_COLORS.get(lang, LANG_COLORS["_default"])
    parts = [
        f'<text x="20" y="34" class="ttl">{_escape(repo["name"])}</text>',
    ]
    for i, l in enumerate(desc):
        parts.append(f'<text x="20" y="{62 + i * 20}" class="desc">{_escape(l)}</text>')
    x = 20
    if lang:
        parts.append(f'<circle cx="{x + 5}" cy="{H - 24}" r="5.5" fill="{color}"/>')
        parts.append(f'<text x="{x + 16}" y="{H - 19}" class="meta">{_escape(lang)}</text>')
        x += 36 + len(lang) * 8
    parts.append(f'<text x="{x}" y="{H - 19}" class="meta">★ {repo.get("stars", 0)}</text>')
    parts.append(f'<text x="{x + 64}" y="{H - 19}" class="meta">⑂ {repo.get("forks", 0)}</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Project {_escape(repo['name'])}">
  <style>
    .bgrect {{ fill: {palette['bg']}; stroke: {palette['border']}; }}
    .ttl {{ fill: {palette['header']}; font-size: 18px; font-weight: 700; }}
    .desc {{ fill: {palette['value']}; font-size: 13px; }}
    .meta {{ fill: {palette['dim']}; font-size: 13px; }}
    .accent {{ fill: {art['accent']}; }}
    text {{ font-family: {FONT_STACK}; }}
  </style>
  <rect class="bgrect" x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10"/>
  <rect class="accent" x="0" y="0" width="{W}" height="4" rx="2" opacity="0.9"/>
  {''.join(parts)}
</svg>'''


CONTRIB_LEVELS = {
    "light": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
    "dark": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
}


def build_contrib_svg(mode, days):
    """GitHub-style contribution heatmap. days: [(iso_date, count), ...] ordered."""
    from datetime import date
    palette = COLORS[mode]
    levels = CONTRIB_LEVELS[mode]
    CELL, GAP, LEFT, TOP = 11, 3, 34, 40
    if not days:
        days = []
    first = date.fromisoformat(days[0][0]) if days else date.today()
    offset = (first.weekday() + 1) % 7          # Sunday-first rows
    peak = max((c for _, c in days), default=0) or 1
    total = sum(c for _, c in days)

    def level(c):
        if c <= 0:
            return 0
        q = c / peak
        return 1 if q <= 0.25 else 2 if q <= 0.5 else 3 if q <= 0.75 else 4

    cells, months, seen = [], [], set()
    for idx, (iso, cnt) in enumerate(days):
        pos = idx + offset
        col, row = divmod(pos, 7)
        x = LEFT + col * (CELL + GAP)
        y = TOP + row * (CELL + GAP)
        d = date.fromisoformat(iso)
        key = (d.year, d.month)
        if row == 0 or idx == 0:
            if key not in seen and d.day <= 7:
                seen.add(key)
                months.append(f'<text x="{x}" y="{TOP - 8}" class="dim" font-size="10">{d.strftime("%b")}</text>')
        cells.append(
            f'<rect class="c" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" '
            f'fill="{levels[level(cnt)]}" style="animation-delay:{col * 0.025:.2f}s"><title>{cnt} on {iso}</title></rect>'
        )
    cols = (len(days) + offset + 6) // 7
    W = LEFT + cols * (CELL + GAP) + 16
    H = TOP + 7 * (CELL + GAP) + 28
    dow = "".join(
        f'<text x="6" y="{TOP + r * (CELL + GAP) + 9}" class="dim" font-size="9">{n}</text>'
        for r, n in ((1, "Mon"), (3, "Wed"), (5, "Fri"))
    )
    legend_x = W - 16 - 5 * (CELL + 3) - 60
    legend = (
        f'<text x="{legend_x}" y="{H - 10}" class="dim" font-size="10">Less</text>'
        + "".join(
            f'<rect x="{legend_x + 28 + i * (CELL + 3)}" y="{H - 19}" width="{CELL}" height="{CELL}" rx="2" fill="{lv}"/>'
            for i, lv in enumerate(levels)
        )
        + f'<text x="{legend_x + 32 + 5 * (CELL + 3)}" y="{H - 10}" class="dim" font-size="10">More</text>'
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Contribution graph">
  <style>{_streak_svg_style(palette)}
    .c {{ animation: pop .5s ease-out backwards; }}
    @keyframes pop {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
  </style>
  <rect class="bgrect" x="0" y="0" width="{W}" height="{H}" rx="10"/>
  <text x="16" y="22" class="hdr" font-size="14">{total:,} contributions in the last year</text>
  {''.join(months)}{dow}{''.join(cells)}{legend}
</svg>'''


if __name__ == "__main__":
    # Quick local preview with placeholder numbers, so you can see the
    # layout before wiring up the real GitHub Action.
    demo_stats = {
        "repos_owned": 95,
        "repos_contributed": 133,
        "stars": 342,
        "commits": 2116,
        "followers": 196,
        "loc_total": 446276,
        "loc_added": 523178,
        "loc_deleted": 76902,
    }
    demo_trophy_stats = {
        "stars": 342, "commits": 2116, "followers": 196, "issues": 12,
        "pull_requests": 34, "repositories": 95, "reviews": 5,
        "languages": 14, "organizations": 2, "created_at": "2021-01-01T00:00:00Z",
    }
    demo_streak = {"current": 3, "longest": 12, "total": 1487}
    demo_langs = [
        {"name": "Jupyter Notebook", "bytes": 5266111, "percent": 76.1},
        {"name": "Python", "bytes": 1368564, "percent": 19.8},
        {"name": "PLpgSQL", "bytes": 27051, "percent": 0.4},
        {"name": "TeX", "bytes": 18170, "percent": 0.3},
        {"name": "Shell", "bytes": 9966, "percent": 0.1},
        {"name": "Dockerfile", "bytes": 9599, "percent": 0.1},
    ]
    out_dir = os.path.join(HERE, "..")
    for mode in ("light", "dark"):
        svg = build_combined_svg(mode, demo_stats)
        with open(os.path.join(out_dir, f"{mode}_mode.svg"), "w", encoding="utf-8") as f:
            f.write(svg)
        trophy_svg = build_trophies_svg(mode, demo_trophy_stats)
        with open(os.path.join(out_dir, f"trophies-{mode}.svg"), "w", encoding="utf-8") as f:
            f.write(trophy_svg)
        streak_svg = build_streak_svg(mode, demo_streak)
        with open(os.path.join(out_dir, f"streak-{mode}.svg"), "w", encoding="utf-8") as f:
            f.write(streak_svg)
        langs_svg = build_top_langs_svg(mode, demo_langs)
        with open(os.path.join(out_dir, f"top-langs-{mode}.svg"), "w", encoding="utf-8") as f:
            f.write(langs_svg)
        for name, svg in (("header", build_header_svg(mode)), ("quote", build_quote_svg(mode))):
            with open(os.path.join(out_dir, f"{name}-{mode}.svg"), "w", encoding="utf-8") as f:
                f.write(svg)
    print("Wrote light_mode.svg, dark_mode.svg, trophies-*.svg, streak-*.svg and top-langs-*.svg, header-*.svg and quote-*.svg with placeholder stats.")