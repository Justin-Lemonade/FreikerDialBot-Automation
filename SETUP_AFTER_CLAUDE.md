# SETUP_AFTER_CLAUDE.md

This file is for you (the repo owner), not for AI agents. It lists only
actions that require your manual intervention — things outside what
Claude (or another agent) can safely do through repository access alone.

Last updated: 2026-07-23, against commit `f2e6acc5c5dd6e227d77fa4196f2cc7ac0906b7c`.

---

## REQUIRED NOW

### 1. Decide what to do about 80 tracked files under `data/`

**Why you need to do this:** The initial commit accidentally included 80
files under `data/` — a `bot.log`, 12 JPEG images (27–227 KB, real-sized,
Telegram file-ID-style filenames), and export files. `.gitignore` now
excludes `/data/` going forward, but that doesn't remove files already in
git history — anyone who clones the repo still gets these files and can
see them in past commits even after I untrack them from future commits.

I've already run `git rm -r --cached data/` in this pass, which stops
these files from being included in *new* commits — but the files still
exist in the repository's git history and would need a history rewrite
(e.g. `git filter-repo` or GitHub's own history-purge tooling) to be
fully removed. **I'm not doing that automatically** — rewriting history
changes every commit hash after the rewrite point, which could break
anything (local clones, forks, CI caches, links to specific commits) that
references the old hashes. That's a decision with real consequences only
you should make.

**Exact steps:**
1. Look at what's actually in the JPEGs first — I did not open them.
   Locally: `git show 2ead73c:data/AQADRgxrG_TgaEZ9.jpg > /tmp/check.jpg`
   (repeat for others), then view them. Confirm whether they're real
   customer-related photos or harmless test images.
2. If they're sensitive: use [GitHub's guide on removing sensitive
   data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
   or `git filter-repo` to purge them from history, then force-push.
   Since this is a solo-owner repo with no other clones/forks you need
   to worry about, this is lower-risk than it would be on a shared repo
   — but still worth doing deliberately, not automatically.
3. If they're not sensitive: no history rewrite needed — the
   already-completed `git rm --cached` is enough; just don't add new
   files under `data/` going forward (the `.gitignore` rule now prevents
   this automatically).

**What success looks like:** Either the sensitive files no longer appear
anywhere in `git log --all -- data/`, or you've confirmed they're
harmless and decided to leave history as-is.

**How to verify:** `git log --all --oneline -- data/AQADRgxrG_TgaEZ9.jpg`
(or any of the other filenames) — if you rewrite history, this should
return nothing after the rewrite.

**Required now or optional:** Required now if the images turn out to
contain real customer data. Optional (but still worth deciding
consciously) if they're harmless.

---

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
