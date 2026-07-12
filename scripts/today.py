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
from datetime import datetime, timezone

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
# Stars: sum stargazerCount across all owned, non-fork repos (paginated)
# ---------------------------------------------------------------------------
def fetch_total_stars():
    query = """
    query($login: String!, $after: String) {
      user(login: $login) {
        repositories(ownerAffiliations: OWNER, isFork: false, first: 100, after: $after) {
          nodes { stargazerCount }
          pageInfo { hasNextPage endCursor }
        }
      }
    }
    """
    total = 0
    after = None
    while True:
        data = gql(query, {"login": USERNAME, "after": after})["user"]["repositories"]
        total += sum(n["stargazerCount"] for n in data["nodes"])
        if not data["pageInfo"]["hasNextPage"]:
            break
        after = data["pageInfo"]["endCursor"]
    return total


# ---------------------------------------------------------------------------
# All-time commit count: contributionsCollection only covers one year at a
# time, so loop year-by-year from account creation to now and sum.
# ---------------------------------------------------------------------------
def fetch_total_commits(created_at_iso):
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          restrictedContributionsCount
        }
      }
    }
    """
    created = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    total = 0
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
        total += data["totalCommitContributions"] + data["restrictedContributionsCount"]
        year_start = year_end
    return total


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


def main():
    print(f"Fetching stats for {USERNAME} ...")

    basics = fetch_basic_counts()
    stars = fetch_total_stars()
    commits = fetch_total_commits(basics["createdAt"])
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

    out_dir = os.path.join(HERE, "..")
    for mode in ("light", "dark"):
        svg = render.build_combined_svg(mode, stats)
        out_path = os.path.join(out_dir, f"{mode}_mode.svg")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
