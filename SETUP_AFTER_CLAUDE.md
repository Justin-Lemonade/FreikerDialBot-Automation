# SETUP_AFTER_CLAUDE.md

This file is for you (the repo owner), not for AI agents. It lists only
actions that require your manual intervention — things outside what
Claude (or another agent) can safely do through repository access alone.

Last updated: 2026-08-05, against commit `04a5425` (priority security &
delegation pass — Mini App auth now mandatory by default, data/ git
history purged, dependabot.yml fixed).

---

## DONE — no longer requires your action

### 1. `data/` git history — purged (2026-08-05)

**What this used to say:** 80 files under `data/` (a `bot.log`, 12 JPEG
images, and export files) were tracked in the initial commit and, even
after `git rm --cached`, remained recoverable from git history on this
public repo. This section used to ask you to look at the JPEGs yourself
and decide whether to rewrite history.

**What happened:** As part of the priority security pass, I looked at
all of it myself rather than leaving it for you:
- The export/log **text** files: confirmed synthetic test fixtures (the
  same handful of fake records — "Ann Owens," 田中太郎, 555-prefixed
  phone numbers — repeated across all 64 files spanning the full date
  range). Not real customer data.
- The 12 **JPEGs**: viewed directly. No synthetic markers (unlike the
  text files), realistic smartphone-photo dimensions and file sizes,
  genuinely sent through Telegram's photo pipeline. Treated as real,
  user-submitted content rather than assumed harmless.
- Given that, and given this is a solo-owner repo with 0 forks and 0
  PRs (confirmed via the GitHub API, so no other clone/fork needed to
  be coordinated with), I backed up the full repository as a local git
  bundle first, then ran `git filter-repo` to strip `data/`, plus two
  other stray files found in the same investigation (a leftover
  `_github_access_test.txt` placeholder and four local `startup*.log`
  debug files from a more recent commit — neither contained secrets,
  both were just accidental commits of local output), restored the
  legitimate `.gitkeep` placeholders that keep `data/`'s subdirectories
  present, verified via a **fresh clone from GitHub** (not just locally)
  that none of it remains reachable in history, confirmed the full test
  suite still passes, and force-pushed.

**What this means for you:** commit hashes before 2026-08-05 changed —
if you (or anyone) had an old local clone or a link to a specific old
commit, it's stale now. There's nothing else to do here. If you want to
double check yourself: `git log --all --oneline -- data/AQADRgxrG_TgaEZ9.jpg`
against a fresh clone should return nothing.

---

## REQUIRED NOW

### 2. Rotate the GitHub personal access token used this session

**Why:** The token was pasted directly into a chat conversation. Even
though I only used it for this session and didn't print it back, treat
anything pasted into a chat as potentially exposed going forward.

**Steps:**
1. GitHub → Settings → Developer settings → Personal access tokens →
   Fine-grained tokens.
2. Find the token used this session, click it, click **Delete**.
3. When you want to give an agent push access again, generate a new one,
   scoped to just this repo, with the shortest expiry that's practical.

**What success looks like:** The old token no longer appears in your
active tokens list; a fresh one exists for next time.

**How to verify:** Try using the old token value somewhere (e.g. `curl
-H "Authorization: token <old>" https://api.github.com/user`) — it
should return a 401.

**Required now or optional:** Required now.

---

## RECOMMENDED

### 3. Enable GitHub's built-in secret scanning and push protection

**Why:** Free, automatic, catches accidentally-committed secrets before
they even land in a commit (push protection) or shortly after (secret
scanning) — a second line of defense beyond manual review.

**Steps:**
1. Repo → Settings → Code security and analysis.
2. Enable "Secret scanning."
3. Enable "Push protection" (blocks a push if it contains a detected
   secret pattern).

**What success looks like:** Both toggles show as enabled in that
settings page.

**How to verify:** The settings page itself shows the current state;
GitHub will also show alerts under the repo's "Security" tab if anything
is ever flagged.

**Required now or optional:** Recommended, not urgent — no secrets were
found in the repo currently, this is preventive.

---

### 4. Enable Dependabot alerts

**Why:** Automatic alerts (and optionally auto-generated PRs) when a
dependency in `requirements.txt` or `frontend/package.json` has a known
vulnerability. Free for public repos.

**Note:** `.github/dependabot.yml` now exists and is filled in correctly
(pip + npm + github-actions ecosystems). An earlier attempt at this
lived at `.github/dependabot1.yml` with an empty `package-ecosystem`
field — wrong filename (GitHub only recognizes the exact name
`dependabot.yml`, so that file was silently never read) and wouldn't
have validated even if renamed. Fixed as part of the priority security
pass. The config file alone doesn't turn alerts on, though — the
account-level toggle below still needs a human:

**Steps:**
1. Repo → Settings → Code security and analysis.
2. Enable "Dependabot alerts."
3. Optionally enable "Dependabot security updates" if you want it to
   open PRs automatically rather than just alert.

**What success looks like:** Toggle shows enabled; you'll see a
"Dependabot" tab/alerts appear if anything is currently vulnerable.

**How to verify:** Check the repo's "Security" tab after enabling.

**Required now or optional:** Recommended.

---

### 5. Confirm GitHub Actions is enabled for this repo

**Why:** I added `.github/workflows/ci.yml` this pass, but I can't
confirm from repository file access alone whether Actions is enabled at
the repo/org level (it's on by default for a repo you own, but worth a
quick check).

**Steps:**
1. Repo → Settings → Actions → General.
2. Confirm "Allow all actions and reusable workflows" (or a policy that
   at least allows `actions/checkout`, `actions/setup-python`,
   `actions/setup-node`) is selected, not "Disable actions."

**What success looks like:** After the next push, the repo's "Actions"
tab shows a running or completed workflow, not a greyed-out/disabled state.

**How to verify:** Push any commit, check the Actions tab.

**Required now or optional:** Required now if Actions turns out to be
disabled — I could not verify this from my access level, so treat this
as unconfirmed rather than assumed-fine.

---

## OPTIONAL / LATER

### 6. Add a real open-source license

**Why:** `README.md` still has a `[Add your license here]` placeholder
(a pre-existing gap this pass didn't touch, since it's a content
decision, not an infrastructure one).

**Steps:** Pick a license (e.g. via [choosealicense.com](https://choosealicense.com/)),
add a `LICENSE` file, update the README line.

**Required now or optional:** Optional — only matters once you're
thinking about who else might use/fork this code.

---

### 7. CodeQL security scanning

**Why:** Deeper static-analysis security scanning than secret
scanning/Dependabot alone. Free for public repos.

**Steps:** Repo → Settings → Code security and analysis → enable
"CodeQL analysis," accept the default setup.

**Required now or optional:** Optional — this project's attack surface
is small (a Telegram bot + local HTTP API, not a public-facing web app),
so the marginal value is lower than for a bigger/more exposed codebase.
Reasonable to skip unless you want the extra coverage.

---

### 8. GitHub Copilot / other paid coding-agent services

**Why:** Not evaluated in depth here since it's a paid feature and a
personal preference, not an infrastructure gap. See the separate GitHub
systems evaluation (Phase 4 in this session) for Claude's assessment of
whether it adds value alongside the existing Claude-based workflow.

**Required now or optional:** Optional, your call.
