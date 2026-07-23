# PROJECT_STATUS.md

Last verified against commit: f2e6acc5c5dd6e227d77fa4196f2cc7ac0906b7c
Last updated: 2026-07-23

Quick-reference state for a new AI session. For architecture and rules,
see `AGENTS.md`. For the full open-issues list, see `BACKLOG.md`. This
file only answers "where are we right now" — it does not duplicate either.

## What is the project?

Telegram bot + Mini App for running a debt-collection calling queue. See
`AGENTS.md` for the one-paragraph description and architecture.

## What is complete?

- Backend: full Mini App HTTP API (16 endpoints), Telegram initData auth,
  search/edit/blacklist/history, admin export with authorization.
- Frontend: `frontend/src` is built — App.tsx, api client, 4 hooks, 5
  pages, 6 components. Typechecks clean, production build succeeds.
- Developer infrastructure (this pass): `AGENTS.md`, this file, CI
  workflow, doc corrections, `SETUP_AFTER_CLAUDE.md`.

## What is currently being worked on?

Nothing mid-flight. The last completed unit of work was this
infrastructure/workflow pass (CI, `AGENTS.md`, documentation
reconciliation) — no feature work is in progress.

## What is next?

See `BACKLOG.md`'s "Still open" section for the full list, in priority
order roughly:
1. Frontend test coverage (currently zero automated tests for `frontend/src`).
2. Wiring blacklist-awareness into the *mutating* queue-advance path
   (`next_customer()`), not just the read-only peek (`BACKLOG.md` #13).
3. Mini-App-side import flow (currently Telegram-only).

## What is blocked?

Nothing is blocked on external dependencies. The `data/` git-history
question (see below) is blocked on a decision only the repo owner can
make — see `SETUP_AFTER_CLAUDE.md`.

## What is known to be broken?

- `test_import_pipeline.py::TestMalformedAndAdversarialInputs::test_bare_scalar_text_is_routed_to_ai_parser_not_json_validation`
  — pre-existing failure, confirmed across multiple passes, not
  introduced by any recent work. Not currently blocking anything (excluded
  from the "251 passed" count below intentionally — see that test file
  for why it's a known, accepted gap).

## What was last verified, and how?

- **Commit:** `f2e6acc5c5dd6e227d77fa4196f2cc7ac0906b7c`
- **Backend tests:** 251 passed, 0 failed — run directly against a fresh
  clone of this commit, not assumed from a prior session.
- **Frontend:** `tsc -b --noEmit` clean, `npm run build` succeeds — same,
  run fresh against this commit.
- **CI:** Did not exist before this pass. Added in `.github/workflows/ci.yml`
  — check the Actions tab for its result on this commit going forward,
  rather than re-running the full suite manually every session.

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
