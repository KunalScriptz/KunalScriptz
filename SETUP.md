# Setup — one-time, ~10 minutes

## 1. File layout
Copy everything in this folder into the root of your `KunalScriptz/KunalScriptz`
profile repo, keeping the structure:

```
KunalScriptz/
├── README.md
├── light_mode.svg          <- placeholder, overwritten by the Action
├── dark_mode.svg            <- placeholder, overwritten by the Action
├── assets/
│   ├── ascii-light.svg
│   └── ascii-dark.svg
├── scripts/
│   ├── today.py
│   ├── render.py
│   └── requirements.txt
├── cache/                    <- created empty; the Action fills it in
└── .github/workflows/update-readme.yml
```

## 2. Create a Personal Access Token
The default `GITHUB_TOKEN` that Actions gives you can't read your private
repos or full contribution history, so you need a real PAT:

1. GitHub → Settings → Developer settings → **Personal access tokens** →
   Tokens (classic) → Generate new token
2. Scopes: `repo`, `read:user`, `user:email`
3. Copy the token — you won't see it again

## 3. Add repo secrets
In `KunalScriptz/KunalScriptz` → Settings → Secrets and variables → Actions:

| Secret name | Value |
|---|---|
| `ACCESS_TOKEN` | the PAT you just generated |
| `AUTHOR_EMAILS` | comma-separated list of every email you commit with, e.g. `kunal1520018@gmail.com,12345678+KunalScriptz@users.noreply.github.com` |

To find your GitHub noreply email: Settings → Emails → "Keep my email addresses
private" section shows it. Include it, or commits made through the GitHub
web UI won't be counted.

## 4. Run it
Go to the **Actions** tab → "Update profile stats card" → **Run workflow**.
First run will be slow (cloning every repo to sum line changes); after that,
the `cache/` folder makes repeat runs skip anything unchanged.

It's scheduled to re-run daily at 03:15 UTC after that — edit the cron line
in `update-readme.yml` if you want it more/less often.

## 5. Adjust your bio fields any time
Open `scripts/render.py` and edit the `BIO` dict at the top — OS, host,
hobbies, contact links, and `WORK_START_DATE` for the auto-incrementing
uptime line. These are static and don't need the Action to change; just
edit, commit, and the next run (or a manual trigger) picks it up.

## Notes / things worth knowing
- Counting lines of code by cloning every repo is exactly what makes this
  "real" instead of a badge estimate — but it means the first run can take
  a while if you have many/large repos. That's expected.
- If a repo is huge and you don't want it counted, remove it from the
  `ownerAffiliations` query in `today.py`'s `list_all_repo_urls`, or just
  exclude specific `nameWithOwner` values in that function.
- The README uses a `<picture>` element with `prefers-color-scheme` media
  queries — this is the same mechanism GitHub's own docs recommend for
  auto light/dark images, and is more reliable across viewers than relying
  on `@media` rules inside a single embedded SVG.
