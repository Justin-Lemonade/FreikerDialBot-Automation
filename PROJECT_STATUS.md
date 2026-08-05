# PROJECT_STATUS.md

Last verified against commit: 04a5425 (priority security & delegation
pass)
Last updated: 2026-08-05

Quick-reference state for a new AI session. For architecture and rules,
see `AGENTS.md`. For the full open-issues list, see `BACKLOG.md`. This
file only answers "where are we right now" — it does not duplicate either.

## What happened in the priority security & delegation pass (2026-08-05)

- **`data/` git history purged.** The 80 files flagged in
  `SETUP_AFTER_CLAUDE.md` (12 JPEGs + 64 synthetic export fixtures +
  `bot.log`) are no longer recoverable from history — backed up first,
  purged with `git filter-repo`, verified via a fresh clone, force-pushed.
  Full writeup moved to `SETUP_AFTER_CLAUDE.md`'s "DONE" section.
- **Mini App API auth is now mandatory by default**, not opt-in.
  Missing/malformed credentials → 401 on every real endpoint; `/` and
  static assets stay open. See `MINI_APP_API.md` and `AGENTS.md`'s
  architecture section.
- Two regressions from an earlier commit fixed: `bot.py`'s missing
  `__main__` guard (the app's documented entry point did nothing) and a
  `--no-mini-app`/`--no-mini_app` flag typo.
- `.github/dependabot.yml` fixed — a previous attempt lived at the wrong
  filename (`dependabot1.yml`, silently never read by GitHub) with an
  empty config.

## What is the project?

Telegram bot + Mini App for running a debt-collection calling queue. See
`AGENTS.md` for the one-paragraph description and architecture.

## What is complete?

- Backend: full Mini App HTTP API (16 endpoints), Telegram initData auth,
  search/edit/blacklist/history, admin export with authorization.
- Frontend: `frontend/src` is built — App.tsx, api client, 4 hooks, 5
  pages, 6 components. Typechecks clean, production build succeeds.
- Developer infrastructure: `AGENTS.md`, this file, CI workflow, doc
  corrections, `SETUP_AFTER_CLAUDE.md`.
- **Mini App launch path (fixed and consolidated this pass):**
  `python bot.py` alone now builds the frontend, starts the Mini App
  backend (serving that build via `MINI_APP_STATIC_DIR`), and starts an
  ngrok tunnel if available -- confirmed live, not just in unit tests
  (see `AGENTS.md`'s launch-path notes). Previously the launcher
  (`start_mini_app.py`) never built or served the frontend at all, and
  the frontend's default API URL would have been unreachable from a
  real phone even if it had. Both root-caused and fixed.
- Blacklist-vs-completion bug fixed: a queue whose only remaining
  customer was blacklisted could never auto-complete (confirmed live,
  fixed, regression-tested).
- Duplicate outcome-submission protection confirmed safe and now has
  regression test coverage (previously unverified by any test).

## What is currently being worked on?

Nothing mid-flight. The last completed unit of work was verifying and
fixing the actual Mini App launch path end-to-end (frontend build,
backend static-serving, ngrok tunnel handling) and consolidating it so
`python bot.py` is the single entrypoint for the whole stack.

## What is next?

See `BACKLOG.md`'s "Still open" section for the full list, in priority
order roughly:
1. Real Telegram device verification -- everything up to "does a real
   phone actually load the Mini App" is now verified; that specific
   step requires a real device and cannot be done from an AI sandbox
   (no network access to Telegram's or ngrok's servers).
2. Frontend test coverage (currently zero automated tests for `frontend/src`).
3. Wiring blacklist-awareness into the *mutating* queue-advance path
   (`next_customer()`), not just the read-only peek (`BACKLOG.md` #13).
3. Mini-App-side import flow (currently Telegram-only).

## What is blocked?

Nothing is blocked on external dependencies. The `data/` git-history
question (see below) is blocked on a decision only the repo owner can
make — see `SETUP_AFTER_CLAUDE.md`.

## What is known to be broken?

- Nothing currently. As of this pass, CI's "Backend tests (Python)" job
  had failed on **every run since CI was introduced** (7/7, always at
  test collection, never at an actual test) — root-caused and fixed this
  pass. See `BACKLOG.md`'s Resolved section for the full explanation;
  short version: bare `pytest` (what CI runs) couldn't import repo-root
  modules, only `python -m pytest` (what past sessions ran locally)
  could. Fixed with `pytest.ini` (`pythonpath = .`), no CI YAML change
  needed.
- `test_import_pipeline.py::TestMalformedAndAdversarialInputs::test_bare_scalar_text_is_routed_to_ai_parser_not_json_validation`
  — previously documented here as a confirmed, persistent failure. Now
  passes consistently (3/3) with no changes to the files it exercises.
  Left as an open discrepancy rather than declared "fixed" — see
  `BACKLOG.md` item 16.

## What was last verified, and how?

- **Commit:** `04a5425` (priority security & delegation pass)
- **Backend tests:** 309 passed, 0 failed — run directly against a fresh
  clone of this commit, not assumed from a prior session. Verified with
  *both* `python -m pytest tests/ -q` and bare `pytest tests/ -q`, with
  CI's exact dummy env vars.
- **Frontend:** typechecks clean (`tsc -b --noEmit`), production build
  succeeds, re-verified this pass after the phone-blacklisting and
  reference-mockup UI changes.
- **CI:** frontend job now includes a lint step (oxlint), added in the
  documentation-freshness pass. Check the Actions tab to confirm it's
  green on this commit, not just this local reproduction.

## Known documentation drift (see AGENTS.md for the full rule)

- `set_active_customer` was documented as implemented in 3 files but
  does not exist in code. Corrected this pass.
- `POST /call/return` was documented as implemented but does not exist
  as a route. Corrected this pass.
- `SECURITY_AUDIT_REPORT.md` claimed `data/` was fully gitignore-excluded
  and git history was clean. Neither was true — 80 files were tracked
  under `data/`. Corrected this pass; remediation is in
  `SETUP_AFTER_CLAUDE.md`.

## What should the next AI session do?

1. `git pull` — don't trust local/previous-session state (see `AGENTS.md`).
2. Check the Actions tab for the latest CI result before re-running tests
   yourself.
3. Read this file and `AGENTS.md` before doing a fresh full audit — if
   both are current (check "Last verified against commit" against
   `git log -1`), you likely don't need to re-derive architecture from
   scratch.
4. If picking up feature work, start from `BACKLOG.md`'s "Still open"
   list rather than assuming what's next.
