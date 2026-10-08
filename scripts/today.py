"""
today.py
--------
Computes real GitHub stats for a user (repos, contributed-to repos, stars,
all-time commits, followers, and total lines of code added/removed across
every owned + contributed repo), then renders light_mode.svg / dark_mode.svg
via render.py.

Meant to run inside GitHub Actions (see .github/workflows/update-readme.yml),
but you can also run it locally with the right environment variables set,
e.g. for testing:

    export ACCESS_TOKEN=ghp_xxx
    export GITHUB_ACTOR=KunalScriptz
    export AUTHOR_EMAILS="kunal1520018@gmail.com,you@users.noreply.github.com"
    python scripts/today.py

Required PAT scopes: repo, read:user, user:email
(public_repo is not enough if you want private-repo stats included).
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone

import requests

import render

GITHUB_API = "https://api.github.com/graphql"
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "..", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def env(name, default=None, required=False):
    val = os.environ.get(name, default)
    if required and not val:
        sys.exit(f"Missing required environment variable: {name}")
    return val


TOKEN = env("ACCESS_TOKEN", required=True)
USERNAME = env("GITHUB_ACTOR", required=True)
AUTHOR_EMAILS = [e.strip() for e in env("AUTHOR_EMAILS", "").split(",") if e.strip()]

HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def gql(query, variables=None):
    resp = requests.post(
        GITHUB_API, json={"query": query, "variables": variables or {}}, headers=HEADERS
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


# ---------------------------------------------------------------------------
# Basic counts: followers, owned repos, contributed-to repos
# ---------------------------------------------------------------------------
def fetch_basic_counts():
    query = """
    query($login: String!) {
      user(login: $login) {
        createdAt
        followers { totalCount }
        repositories(ownerAffiliations: OWNER, isFork: false, first: 1) {
          totalCount
        }
        repositoriesContributedTo(
          includeUserRepositories: false
          contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, REPOSITORY]
        ) {
          totalCount
        }
      }
    }
    """
    data = gql(query, {"login": USERNAME})["user"]
    return data


# ---------------------------------------------------------------------------
# Stars + language count: sum stargazerCount and collect the set of unique
# languages across all owned, non-fork repos (paginated).
# ---------------------------------------------------------------------------
def fetch_repo_aggregates():
    query = """
    query($login: String!, $after: String) {
      user(login: $login) {
        repositories(ownerAffiliations: OWNER, isFork: false, first: 100, after: $after) {
          nodes {
            stargazerCount
            languages(first: 30) { nodes { name } }
          }
          pageInfo { hasNextPage endCursor }
        }
      }
    }
    """
    total = 0
    languages = set()
    after = None
    while True:
        data = gql(query, {"login": USERNAME, "after": after})["user"]["repositories"]
        for n in data["nodes"]:
            total += n["stargazerCount"]
            for lang in ((n.get("languages") or {}).get("nodes") or []):
                if lang and lang.get("name"):
                    languages.add(lang["name"])
        if not data["pageInfo"]["hasNextPage"]:
            break
        after = data["pageInfo"]["endCursor"]
    return total, len(languages)


# ---------------------------------------------------------------------------
# All-time commit + review count: contributionsCollection only covers one year
# at a time, so loop year-by-year from account creation to now and sum.
# ---------------------------------------------------------------------------
def fetch_contribution_totals(created_at_iso):
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          restrictedContributionsCount
          totalPullRequestReviewContributions
        }
      }
    }
    """
    created = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    commits = 0
    reviews = 0
    year_start = created
    while year_start < now:
        year_end = min(
            year_start.replace(year=year_start.year + 1), now
        )
        data = gql(
            query,
            {
                "login": USERNAME,
                "from": year_start.isoformat(),
                "to": year_end.isoformat(),
            },
        )["user"]["contributionsCollection"]
        commits += data["totalCommitContributions"] + data["restrictedContributionsCount"]
        reviews += data["totalPullRequestReviewContributions"]
        year_start = year_end
    return commits, reviews


# ---------------------------------------------------------------------------
# Trophy-only counts: authored issues, authored pull requests, and org
# memberships. `totalCount` on each connection means no pagination needed.
# ---------------------------------------------------------------------------
def fetch_social_counts():
    query = """
    query($login: String!) {
      user(login: $login) {
        issues { totalCount }
        pullRequests { totalCount }
        organizations { totalCount }
      }
    }
    """
    data = gql(query, {"login": USERNAME})["user"]
    return {
        "issues": data["issues"]["totalCount"],
        "pull_requests": data["pullRequests"]["totalCount"],
        "organizations": data["organizations"]["totalCount"],
    }


# Languages excluded from the top-languages card (matches the previous README
# `hide=` list). Matching is case-insensitive.
HIDDEN_LANGS = {"javascript", "css", "scss", "xslt", "typescript", "html"}


# ---------------------------------------------------------------------------
# Streak: pull the contribution calendar year-by-year (calendar only spans
# ~1 year per request) and derive current streak, longest streak, and the
# all-time total contribution count.
# ---------------------------------------------------------------------------
def fetch_streak(created_at_iso):
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }
    """
    created = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    counts = {}
    total = 0
    year_start = created
    while year_start < now:
        year_end = min(year_start.replace(year=year_start.year + 1), now)
        data = gql(
            query,
            {"login": USERNAME, "from": year_start.isoformat(), "to": year_end.isoformat()},
        )["user"]["contributionsCollection"]["contributionCalendar"]
        total += data["totalContributions"]
        for week in data["weeks"]:
            for d in week["contributionDays"]:
                counts[d["date"]] = d["contributionCount"]
        year_start = year_end

    # Current streak ends today — or yesterday if today has no contributions yet.
    today = date.today()
    current = 0
    d = today
    if counts.get(d.isoformat(), 0) == 0:
        d -= timedelta(days=1)
    while counts.get(d.isoformat(), 0) > 0:
        current += 1
        d -= timedelta(days=1)

    longest = 0
    if counts:
        run = 0
        d = date.fromisoformat(min(counts))
        end = date.fromisoformat(max(counts))
        while d <= end:
            if counts.get(d.isoformat(), 0) > 0:
                run += 1
                longest = max(longest, run)
            else:
                run = 0
            d += timedelta(days=1)

    return {"current": current, "longest": longest, "total": total}


# ---------------------------------------------------------------------------
# Top languages: sum per-language byte counts (RepositoryLanguages edges)
# across all owned, non-fork repos, drop the HIDDEN_LANGS, and return the
# top `limit` by share.
# ---------------------------------------------------------------------------
def fetch_top_languages(limit=6):
    query = """
    query($login: String!, $after: String) {
      user(login: $login) {
        repositories(ownerAffiliations: OWNER, isFork: false, first: 100, after: $after) {
          nodes { languages(first: 20) { edges { size node { name } } } }
          pageInfo { hasNextPage endCursor }
        }
      }
    }
    """
    totals = {}
    after = None
    while True:
        data = gql(query, {"login": USERNAME, "after": after})["user"]["repositories"]
        for n in data["nodes"]:
            for e in (n["languages"] or {}).get("edges", []) or []:
                if e and e.get("node"):
                    name = e["node"]["name"]
                    totals[name] = totals.get(name, 0) + e["size"]
        if not data["pageInfo"]["hasNextPage"]:
            break
        after = data["pageInfo"]["endCursor"]

    totals = {name: size for name, size in totals.items() if name.lower() not in HIDDEN_LANGS}
    grand = sum(totals.values()) or 1
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])[:limit]
    return [{"name": name, "bytes": size, "percent": size / grand * 100.0} for name, size in ranked]


# ---------------------------------------------------------------------------
# Lines of code: clone every owned + contributed repo and sum `git log
# --numstat` for the configured author emails. Cached per-repo by HEAD sha
# so unchanged repos are skipped on subsequent runs.
# ---------------------------------------------------------------------------
def list_all_repo_urls():
    query = """
    query($login: String!, $after: String) {
      user(login: $login) {
        repositories(first: 100, after: $after, ownerAffiliations: [OWNER, COLLABORATOR], isFork: false) {
          nodes { nameWithOwner isPrivate defaultBranchRef { name } }
          pageInfo { hasNextPage endCursor }
        }
      }
    }
    """
    repos = []
    after = None
    while True:
        data = gql(query, {"login": USERNAME, "after": after})["user"]["repositories"]
        repos.extend(data["nodes"])
        if not data["pageInfo"]["hasNextPage"]:
            break
        after = data["pageInfo"]["endCursor"]
    return repos


def remote_head_sha(name_with_owner, branch):
    url = f"https://{TOKEN}@github.com/{name_with_owner}.git"
    out = subprocess.run(
        ["git", "ls-remote", url, f"refs/heads/{branch or 'HEAD'}"],
        capture_output=True, text=True,
    )
    if out.returncode != 0 or not out.stdout.strip():
        return None
    return out.stdout.split()[0]


def clone_and_count(name_with_owner):
    url = f"https://{TOKEN}@github.com/{name_with_owner}.git"
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(
            ["git", "clone", "--quiet", url, tmp],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            print(f"  ! clone failed for {name_with_owner}: {r.stderr.strip()[:200]}")
            return 0, 0

        added, deleted = 0, 0
        for email in AUTHOR_EMAILS:
            log = subprocess.run(
                ["git", "log", f"--author={email}", "--pretty=tformat:", "--numstat"],
                cwd=tmp, capture_output=True, text=True,
            )
            for line in log.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
                    added += int(parts[0])
                    deleted += int(parts[1])
        return added, deleted


def fetch_loc_stats(repos):
    total_added, total_deleted = 0, 0
    for repo in repos:
        name = repo["nameWithOwner"]
        branch = (repo.get("defaultBranchRef") or {}).get("name")
        cache_path = os.path.join(CACHE_DIR, name.replace("/", "_") + ".json")

        sha = remote_head_sha(name, branch)
        cached = None
        if os.path.exists(cache_path):
            with open(cache_path) as f:
                cached = json.load(f)

        if cached and sha and cached.get("sha") == sha:
            added, deleted = cached["added"], cached["deleted"]
            print(f"  = {name}: cached ({added}++, {deleted}--)")
        else:
            print(f"  > {name}: computing ...")
            added, deleted = clone_and_count(name)
            with open(cache_path, "w") as f:
                json.dump({"sha": sha, "added": added, "deleted": deleted}, f)
            print(f"    {name}: {added}++, {deleted}--")

        total_added += added
        total_deleted += deleted

    return total_added, total_deleted


# ---------------------------------------------------------------------------
# README extras: featured projects, last-year contribution calendar, recent
# public activity and latest Medium posts. Everything public-only.
# ---------------------------------------------------------------------------
PROJECT_COUNT = 4
# Shown first, in this order (case-insensitive); remaining slots fall back to
# most-starred. Edit this list to change the featured projects.
PINNED_PROJECTS = ["atlas-ai", "jobforgex", "ML-DL-Projects", "ollama_telegram_bot"]
MEDIUM_HANDLE = render.BIO["Medium"]          # e.g. "@kunal1520018"


def fetch_projects(limit=PROJECT_COUNT):
    """Pinned (PINNED_PROJECTS) then most-starred public, non-fork, non-archived repos (profile repo excluded)."""
    query = """
    query($login: String!) {
      user(login: $login) {
        repositories(privacy: PUBLIC, ownerAffiliations: OWNER, isFork: false, first: 30,
                     orderBy: {field: STARGAZERS, direction: DESC}) {
          nodes {
            name url description isArchived stargazerCount forkCount pushedAt
            primaryLanguage { name }
          }
        }
      }
    }
    """
    nodes = gql(query, {"login": USERNAME})["user"]["repositories"]["nodes"]
    nodes = [n for n in nodes if not n["isArchived"] and n["name"].lower() != USERNAME.lower()]
    # Most-starred / most recently pushed first, then pinned repos pulled to the
    # front in PINNED_PROJECTS order (sort is stable, so the rest keep that order).
    nodes.sort(key=lambda n: (n["stargazerCount"], n["pushedAt"]), reverse=True)
    pinned = [name.lower() for name in PINNED_PROJECTS]
    nodes.sort(key=lambda n: pinned.index(n["name"].lower()) if n["name"].lower() in pinned else len(pinned))
    return [
        {
            "name": n["name"], "url": n["url"], "description": n["description"],
            "language": (n["primaryLanguage"] or {}).get("name"),
            "stars": n["stargazerCount"], "forks": n["forkCount"],
        }
        for n in nodes[:limit]
    ]


def fetch_contribution_days():
    """[(iso_date, count)] for roughly the last 365 days."""
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar { weeks { contributionDays { date contributionCount } } }
        }
      }
    }
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=364)
    cal = gql(query, {"login": USERNAME, "from": start.isoformat(), "to": now.isoformat()})[
        "user"]["contributionsCollection"]["contributionCalendar"]
    days = [(d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]
    return sorted(days)


def fetch_recent_activity(limit=5):
    """Markdown bullets for the latest public pushes and merged PRs."""
    resp = requests.get(
        f"https://api.github.com/users/{USERNAME}/events/public?per_page=60",
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"},
        timeout=30,
    )
    resp.raise_for_status()
    items, seen = [], set()
    for ev in resp.json():
        repo = ev["repo"]["name"]
        link = f"[{repo}](https://github.com/{repo})"
        when = ev["created_at"][:10]
        text = None
        if ev["type"] == "PushEvent":
            commits = ev["payload"].get("commits") or []
            if commits:
                msg = commits[-1]["message"].splitlines()[0][:80]
                text = f"🔨 Pushed to {link} — {msg}"
        elif ev["type"] == "PullRequestEvent" and ev["payload"].get("action") == "closed" \
                and ev["payload"]["pull_request"].get("merged"):
            pr = ev["payload"]["pull_request"]
            text = f"🔀 Merged [#{pr['number']}]({pr['html_url']}) in {link} — {pr['title'][:80]}"
        elif ev["type"] == "CreateEvent" and ev["payload"].get("ref_type") == "repository":
            text = f"✨ Created {link}"
        if text and text not in seen:
            seen.add(text)
            items.append(f"- `{when}` {text}")
        if len(items) >= limit:
            break
    return items


def fetch_medium_posts(limit=3):
    """Latest Medium posts via the public RSS feed (no auth)."""
    import xml.etree.ElementTree as ET
    resp = requests.get(f"https://medium.com/feed/{MEDIUM_HANDLE}", timeout=30,
                        headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    posts = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").split("?")[0]
        when = (item.findtext("pubDate") or "")[5:16]
        if title and link:
            posts.append(f"- 📝 [{title}]({link}) — {when}")
        if len(posts) >= limit:
            break
    return posts


def replace_block(text, name, body):
    """Swap the content between <!-- NAME:START --> and <!-- NAME:END --> markers."""
    start, end = f"<!-- {name}:START -->", f"<!-- {name}:END -->"
    if start not in text or end not in text:
        print(f"README marker {name} not found; skipping")
        return text
    head, rest = text.split(start, 1)
    _, tail = rest.split(end, 1)
    return f"{head}{start}\n{body}\n{end}{tail}"


def picture(base, alt, width=None):
    """<picture> tag that serves the light/dark variant of an SVG."""
    w = f' width="{width}"' if width else ""
    return (
        f'<picture><source media="(prefers-color-scheme: dark)" srcset="{base.format(mode="dark")}">'
        f'<img src="{base.format(mode="light")}" alt="{alt}"{w}></picture>'
    )


def safe(label, fn, default):
    """Run a best-effort fetch; one flaky source must never break the whole run."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: {label} failed ({exc}); keeping previous output")
        return default


def main():
    print(f"Fetching stats for {USERNAME} ...")

    basics = fetch_basic_counts()
    stars, language_count = fetch_repo_aggregates()
    commits, reviews = fetch_contribution_totals(basics["createdAt"])
    social = fetch_social_counts()
    streak = fetch_streak(basics["createdAt"])
    top_langs = fetch_top_languages()
    repos = list_all_repo_urls()

    print(f"Scanning {len(repos)} repos for line-of-code stats "
          f"(this is the slow part on a cold cache) ...")
    added, deleted = fetch_loc_stats(repos)

    stats = {
        "repos_owned": basics["repositories"]["totalCount"],
        "repos_contributed": basics["repositoriesContributedTo"]["totalCount"],
        "stars": stars,
        "commits": commits,
        "followers": basics["followers"]["totalCount"],
        "loc_total": added - deleted,
        "loc_added": added,
        "loc_deleted": deleted,
    }
    print("Stats:", json.dumps(stats, indent=2))

    trophy_stats = {
        "stars": stars,
        "commits": commits,
        "followers": basics["followers"]["totalCount"],
        "issues": social["issues"],
        "pull_requests": social["pull_requests"],
        "repositories": basics["repositories"]["totalCount"],
        "reviews": reviews,
        "languages": language_count,
        "organizations": social["organizations"],
        "created_at": basics["createdAt"],
    }

    out_dir = os.path.join(HERE, "..")

    projects = safe("projects", fetch_projects, None)
    contrib_days = safe("contribution calendar", fetch_contribution_days, None)
    activity = safe("recent activity", fetch_recent_activity, None)
    medium = safe("medium feed", fetch_medium_posts, None)

    os.makedirs(os.path.join(out_dir, "projects"), exist_ok=True)
    for mode in ("light", "dark"):
        for name, builder, arg in (
            ("header", render.build_header_svg, None),
            ("quote", render.build_quote_svg, None),
        ):
            path = os.path.join(out_dir, f"{name}-{mode}.svg")
            with open(path, "w", encoding="utf-8") as f:
                f.write(builder(mode))
        if contrib_days:
            with open(os.path.join(out_dir, f"contrib-{mode}.svg"), "w", encoding="utf-8") as f:
                f.write(render.build_contrib_svg(mode, contrib_days))
        for i, repo in enumerate(projects or []):
            with open(os.path.join(out_dir, "projects", f"project-{i + 1}-{mode}.svg"), "w", encoding="utf-8") as f:
                f.write(render.build_project_svg(mode, repo))

        svg = render.build_combined_svg(mode, stats)
        out_path = os.path.join(out_dir, f"{mode}_mode.svg")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"Wrote {out_path}")

        trophy_svg = render.build_trophies_svg(mode, trophy_stats)
        trophy_path = os.path.join(out_dir, f"trophies-{mode}.svg")
        with open(trophy_path, "w", encoding="utf-8") as f:
            f.write(trophy_svg)
        print(f"Wrote {trophy_path}")

        streak_svg = render.build_streak_svg(mode, streak)
        streak_path = os.path.join(out_dir, f"streak-{mode}.svg")
        with open(streak_path, "w", encoding="utf-8") as f:
            f.write(streak_svg)
        print(f"Wrote {streak_path}")

        langs_svg = render.build_top_langs_svg(mode, top_langs)
        langs_path = os.path.join(out_dir, f"top-langs-{mode}.svg")
        with open(langs_path, "w", encoding="utf-8") as f:
            f.write(langs_svg)
        print(f"Wrote {langs_path}")

    update_readme(projects, activity, medium)


def update_readme(projects, activity, medium):
    path = os.path.join(HERE, "..", "README.md")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if projects:
        cells = [
            f'<a href="{r["url"]}">'
            + picture(f"projects/project-{i + 1}-{{mode}}.svg", r["name"], width="49%")
            + "</a>"
            for i, r in enumerate(projects)
        ]
        text = replace_block(text, "PROJECTS", " ".join(cells))
    if activity:
        text = replace_block(text, "ACTIVITY", "\n".join(activity))
    if medium:
        text = replace_block(text, "BLOG", "\n".join(medium))
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    main()
