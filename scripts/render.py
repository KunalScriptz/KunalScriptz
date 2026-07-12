"""
render.py
---------
Builds the combined "ascii art + neofetch stats panel" SVG in both
light_mode.svg and dark_mode.svg flavors.

This module only knows how to draw. All the *numbers* (repos, stars,
commits, lines of code) are computed in today.py and passed in as a
plain dict, so this file never needs to touch the GitHub API.
"""

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")

# ---------------------------------------------------------------------------
# Static bio fields — edit these whenever your info changes.
# Everything under GitHub Stats is computed automatically by today.py instead.
# ---------------------------------------------------------------------------
BIO = {
    "user_at_host": "kunal@admin",
    "OS": "Windows 11, Android 16, Ubuntu Linux",
    "Host": "Worley",
    "Kernel": "Data Scientist / AI Engineer",
    "Languages.Programming": "Python, Shell Script, PowerShell",
    "Languages.Computer": "HTML, CSS, YAML, Markdown",
    "Languages.Real": "English",
    "Hobbies.Software": "Rooting Android devices, Xposed Framework, console jailbreaking (educational)",
    "Hobbies.Hardware": "Overclocking GPU for best performance",
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
    },
    "dark": {
        "bg": "#0d1117",
        "label": "#e3b341",   # amber
        "value": "#e6edf3",
        "header": "#39d98a",
        "dim": "#7d8590",
    },
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


def _extract_ascii_text_block(svg_path):
    """Pull out just the inner <text ...>...</text> node from a generated
    ascii-art SVG (produced by the ASCII Forge tool), so we can re-embed
    it inside our combined canvas with our own transform/positioning."""
    with open(svg_path, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r"(<text .*?</text>)", content, re.S)
    if not match:
        raise ValueError(f"Could not find <text> block in {svg_path}")
    # Strip the fill color class so our own palette controls it instead.
    inner = match.group(1)
    inner = re.sub(r'class="af-fg"', 'class="art-fg"', inner)
    return inner


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

    ascii_path = os.path.join(ASSETS, f"ascii-{mode}.svg")
    art_text_block = _extract_ascii_text_block(ascii_path)

    ART_NATIVE_W, ART_NATIVE_H = 1188, 742
    FONT_SIZE = 26
    LINE_H = 34
    PAD = 34

    lines = []
    lines.append((BIO["user_at_host"], "header"))
    lines.append(("-" * 34, "dim"))
    lines.append((_dotted_line("OS", BIO["OS"]), "kv"))
    lines.append((_dotted_line("Uptime", _uptime_string()), "kv"))
    lines.append((_dotted_line("Host", BIO["Host"]), "kv"))
    lines.append((_dotted_line("Kernel", BIO["Kernel"]), "kv"))
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

    # Scale the art to fill the panel's height (rather than an arbitrary
    # fixed width), so it reads at a comparable size to the text next to it.
    available_art_h = panel_height - PAD * 2
    scale = min(available_art_h / ART_NATIVE_H, 1.0)
    art_col_w = ART_NATIVE_W * scale
    art_col_h = ART_NATIVE_H * scale

    PANEL_X = art_col_w + PAD * 2
    total_height = panel_height
    total_width = PANEL_X + 720

    def render_kv_line(text, y):
        if ":" in text:
            label, rest = text.split(":", 1)
            # split rest into dots and value: dots end where value (non-dot) begins
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
    .art-fg {{ fill: {palette['value']}; opacity: 0.85; }}
    text {{ font-family: {FONT_STACK}; }}
  </style>
  <rect class="bgrect" x="0" y="0" width="{total_width:.0f}" height="{total_height:.0f}" rx="10"/>
  <g transform="translate({PAD},{PAD}) scale({scale:.5f})">
    {art_text_block}
  </g>
  <text xml:space="preserve" font-size="{FONT_SIZE}">
    {''.join(text_tspans)}
  </text>
</svg>'''
    return svg


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
    out_dir = os.path.join(HERE, "..")
    for mode in ("light", "dark"):
        svg = build_combined_svg(mode, demo_stats)
        with open(os.path.join(out_dir, f"{mode}_mode.svg"), "w", encoding="utf-8") as f:
            f.write(svg)
    print("Wrote light_mode.svg and dark_mode.svg with placeholder stats.")