# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is **KunalScriptz's GitHub profile repo** — the `README.md` is what appears on github.com/KunalScriptz. The repo auto-generates a combined "ASCII art + neofetch-style stats panel" SVG (light/dark variants) via a GitHub Action that runs daily, pulling live stats from the GitHub API.

## Architecture

```
scripts/
  today.py       # Fetches real GitHub stats (GraphQL API + git clone for LOC).
                 # Calls render.build_combined_svg() to write light_mode.svg
                 # and dark_mode.svg. Reads cache/ for per-repo LOC SHA caching.
  render.py      # Pure SVG renderer. Takes a stats dict, produces the combined
                 # SVG. Contains the BIO dict with all static info (OS, host,
                 # hobbies, contact links, WORK_START_DATE). Never touches the
                 # GitHub API — it only knows how to draw.
  requirements.txt  # Only dependency: requests>=2.31.0
assets/
  ascii-light.svg   # ASCII art SVG (light theme) — embedded into the combined card
  ascii-dark.svg    # ASCII art SVG (dark theme)
cache/              # Per-repo JSON files with {sha, added, deleted} to skip
                    # unchanged repos on subsequent LOC runs
.github/workflows/update-readme.yml  # Runs daily at 03:15 UTC + on push to
                    # scripts/** or assets/**. Checks out repo, runs today.py,
                    # commits updated SVGs + cache back.
```

**Data flow:** `today.py` → stats dict → `render.build_combined_svg(mode, stats)` → `light_mode.svg` / `dark_mode.svg` → embedded in README.md.

## Commands

### Generate SVGs locally (with placeholder stats)

```bash
cd scripts && python render.py
```

This writes `light_mode.svg` and `dark_mode.svg` to the repo root using hardcoded demo numbers — no GitHub token needed. Useful for iterating on layout, colors, or BIO fields in `render.py`.

### Generate SVGs with real stats (needs PAT)

```bash
export ACCESS_TOKEN=ghp_xxx
export GITHUB_ACTOR=KunalScriptz
export AUTHOR_EMAILS="kunal1520018@gmail.com,12345678+KunalScriptz@users.noreply.github.com"
python scripts/today.py
```

Required PAT scopes: `repo`, `read:user`, `user:email`. First run is slow (clones every owned + contributed repo to count LOC); subsequent runs use `cache/` to skip unchanged repos.

### Trigger the Action manually

Go to the **Actions** tab → "Update profile stats card" → **Run workflow**. Or push to `scripts/**` or `assets/**` — the workflow triggers on those paths.

## Key conventions

- **Never commit with the Co-Authored-By: Claude line.** All commits use `KunalScriptz <kunal1520018@gmail.com>` identity.
- The README uses a plain `<img>` tag (not `<picture>` with media queries) for the profile card SVG.
- Static bio fields (OS, host, hobbies, contact links, `WORK_START_DATE`) live in `render.py`'s `BIO` dict — edit them there, not in the SVG or README directly.
- The `WORK_START_DATE` in `render.py` drives the auto-incrementing "Uptime" line in the profile card.
- LOC counting uses `git log --author=<email> --numstat` on every owned + contributed repo. If a repo is huge and shouldn't be counted, exclude it in `today.py`'s `list_all_repo_urls()`.
