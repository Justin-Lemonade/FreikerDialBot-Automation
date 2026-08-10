# PROJECT_STATUS.md

Current snapshot of the repository as of the audited `main` tree.

For rules and working conventions, read `AGENTS.md`.
For technical architecture and endpoint details, read `ARCHITECTURE.md`.
For security findings, read `SECURITY_AUDIT_REPORT.md`.
For user-facing overview and setup, read `README.md`.
For frontend UI/UX pass history and design backlog, read `FreikerDialBot_UI_UX_Development_Log.md`.

## Source-of-truth rule

GitHub repository contents are authoritative. Documentation describes intent; live code, tests, GitHub PRs, and current commits determine fact. When documentation conflicts with code, verify the code and update the correct canonical document.

# Delegation Control Center

This is the operational control layer for bounded work that can be delegated to smaller, older, weaker, or less capable coding/review models. Do not create a separate delegation Markdown file.

## Model responsibility rules

### Claude / frontier / user decision territory

Keep these with Claude/frontier-level reasoning or the user unless reduced to a completely mechanical subtask:

- major UI/UX redesigns or new visual systems;
- large frontend or backend features;
- new product workflows;
- architecture or shared-service changes;
- database/schema redesigns or broad migrations;
- authentication/security architecture;
- queue/customer-state semantics;
- complex importer or AI-prompt redesigns;
- cross-cutting refactors;
- product decisions or ambiguous requirements;
- framework/test-architecture selection;
- major dependency migrations with breaking changes.

### Smaller-model territory

Prefer smaller models for:

- isolated bug fixes;
- focused regression tests;
- verification/audits;
- documentation corrections grounded in code;
- mechanical cleanup;
- narrow configuration/dependency checks;
- small deterministic refactors;
- removing verified stale artifacts;
- bounded backend/Telegram/Mini App maintenance;
- reproducing and documenting a suspected bug.

**Delegate implementation complexity, not decision-making.**

## Delegation state machine

`DISCOVERED → ASSESSED → READY TO DELEGATE → DELEGATED → IMPLEMENTED → VERIFIED → COMPLETED`

Other valid states: `BLOCKED`, `ESCALATED`, `DEFERRED`, `SUPERSEDED`, `ALREADY HANDLED`.

A task is not complete merely because an AI reports completion; verification evidence is required.

## Current ownership

| Area | Owner | Rule |
|---|---|---|
| Major UI/UX | Claude/frontier | Do not duplicate with smaller models |
| Major features | Claude/frontier | Do not duplicate |
| Architecture/security decisions | Claude + user | Decision before delegation |
| Product behavior | User + Claude | Never infer |
| Small bounded implementation | Delegation Handler → smaller AI | Explicit acceptance criteria required |
| Verification/audit | Delegation Handler → smaller AI | Preferred smaller-model workload |
| Delegation tracking | Delegation Handler | This section is the source of truth |

## Active delegations

None recorded as active at the time of this audit.

## Delegation record template

```text
DLG-XXX — Short task name
Status: READY TO DELEGATE / DELEGATED / IMPLEMENTED / VERIFIED / COMPLETED
Owner/model:
Parent finding:
Problem:
Evidence:
Scope:
Allowed files:
Forbidden files:
Required result:
Acceptance criteria:
Verification:
Dependencies:
Escalation condition:
Commit/PR:
Last verified:
Notes:
```

# Repository-wide audit — 2026-08-09

## Audit baseline

- Repository: `Justin-Lemonade/FreikerDialBot-Automation`
- Branch audited: `main`
- Audited HEAD: `9f89cf9619f8d454268a3e18a88a2cdca5a5b313`
- Latest commit: `docs: expand delegation control center`
- GitHub open Issues: **0**
- GitHub open Pull Requests: **18**, all currently Dependabot dependency/update PRs
- GitHub code-search index: unavailable/not indexed for this repository, so absence of a search hit is not proof that a pattern is absent.

The audit covered the canonical documentation, repository tree, frontend structure, AI parser, CI configuration, security snapshot, dependency manifests, recent commit history, and GitHub issue/PR state. Recent commits were cross-checked against status documentation to detect work that had already been completed but was still described as open.

## Findings: immediate cleanup / safe smaller-model work

### DLG-005 — Remove stale root security-check utility

- Priority: Medium
- Owner: smaller coding model
- File: `_security_check.py`
- Evidence: the tracked script still scans `BACKLOG.md`, which was intentionally removed during documentation consolidation, and its hard-coded file list no longer represents the current canonical documentation set.
- Why it matters: it is stale repository tooling and can produce misleading security-check results.
- Required result: remove the obsolete script if no current workflow invokes it. If any invocation is found, stop and report rather than changing the workflow.
- Verification: search workflow/scripts for `_security_check.py`; confirm no references; review diff.
- Status: **COMPLETED**

### DLG-006 — Remove empty `_install_err.log` artifact

- Priority: Low
- Owner: smaller coding model
- File: `_install_err.log`
- Evidence: the tracked file is empty and is a generated-looking root-level log artifact. `AGENTS.md` says generated/runtime artifacts must not be committed.
- Required result: delete it and confirm no workflow depends on it.
- Verification: repository search for references; diff review.
- Status: **COMPLETED**

### DLG-007 — Correct stale frontend-testing documentation

- Priority: Medium
- Owner: smaller documentation model
- Files: `PROJECT_STATUS.md`, `FreikerDialBot_UI_UX_Development_Log.md`, `frontend/vitest.config.ts`
- Evidence: `frontend/package.json` has `"test": "vitest run"`; `vitest.config.ts` exists; the repository contains Vitest tests; CI runs `npm run test`. However, the UI/UX log still says no frontend test runner exists, and the Vitest config comment still describes the gap as if it were unresolved.
- Required result: update documentation/comments to state that Vitest is now installed and CI-covered, while accurately describing the current coverage limitations.
- Constraint: do not expand test architecture or add broad tests.
- Verification: compare docs with `package.json`, `vitest.config.ts`, CI, and actual test files.
- Status: **COMPLETED**

### DLG-008 — Correct README frontend-validation instructions

- Priority: Low
- Owner: smaller documentation model
- File: `README.md`
- Evidence: README's frontend-only validation example currently lists `npm ci`, typecheck, and build but omits `npm run test`, while `AGENTS.md` and CI require the Vitest test step.
- Required result: add the current frontend test command without duplicating the full validation policy.
- Status: **COMPLETED**

### DLG-009 — Fix `--no-mini-app` launcher flag mismatch

- Priority: Medium
- Owner: smaller coding model
- Evidence: the launcher documents `--no-mini-app`, but the implementation checks the differently spelled `--no-mini_app` form. This makes the documented switch ineffective.
- Required result: make the implementation accept the documented flag exactly as written, while preserving the existing default behavior and any intentionally supported compatibility form only if current code clearly requires it.
- Scope: launcher/entrypoint only; no Mini App architecture changes.
- Verification: inspect parser/help text and add or run a focused argument-parsing check demonstrating that `--no-mini-app` actually disables Mini App startup.
- Escalation: stop if fixing the flag requires redesigning startup ownership or changing unrelated CLI behavior.
- Status: **COMPLETED**
- Notes: Fix implemented in `bot.py`: extracted a `_should_skip_mini_app(argv)` helper that now checks the documented `--no-mini-app` flag (hyphen), matching the spelling `start_mini_app.py` passes and the comment/log text. The previous check looked for the mis-spelled `--no-mini_app` (underscore) form, making the documented switch ineffective. `DISABLE_MINI_APP=1` override is preserved. Added 6 focused argument-parsing tests in `tests/test_bot_mini_app_launch.py` demonstrating `--no-mini-app` disables Mini App startup. Verified with `pytest tests/` (388 passed).

### DLG-010 — Remove inline Telegram import cleanup opportunity

- Priority: Low
- Owner: smaller coding model
- Evidence: Telegram import handling still contains an inline implementation that can be cleaned up without changing the importer workflow.
- Required result: make the smallest deterministic cleanup possible, preserving behavior exactly.
- Constraint: no importer workflow redesign, parsing changes, or UX changes.
- Verification: focused tests plus diff review.
- Status: **COMPLETED**
- Notes: The inline JSON validation in `telegram_ui.py` has been removed. The `handle_json_file` function now calls `importer.import_text` directly, centralizing the import logic.

## Findings: verification / audit work

### VERIFY-009 — Triage all open Dependabot PRs

- Priority: High
- Owner: smaller review model for mechanical triage; Claude for major migrations
- Current state: 18 named Dependabot dependency branches exist on origin (plus 2 consolidated `multi-*` npm branches), all surfaced as open Dependabot PRs. No GitHub API access was available to this maintenance agent (unauthenticated API returned 403), so the live branch refs themselves were used as the source of truth.
- Triage result (2026-08-10, against `main` HEAD `ce3a147`): **every open Dependabot branch is stale** and cannot be merged as-is.
  - All pip and github-actions branches are based on `2de2386` and are 65 commits behind `main`.
  - All npm branches (including the two `multi-*` consolidated branches) are based on `4e821b4` and are 18 commits behind `main`.
  - Because these branch points predate the DLG-005..010 and VERIFY-013..015 work, merging any npm branch as-is would revert that completed work (re-adding `_security_check.py`/`_install_err.log`, removing the new tests, and reverting `bot.py`/`importer.py`/`mini_app_api.py` changes). The diff of each npm branch against `main` is a large net-revert, not a clean bump.
  - `actions/checkout 4→7` is additionally a direct functional conflict: its branch predates the CI's Node 20→22 bump and the added Unit tests step, and its diff would revert `node-version` back to "20" and delete the `npm run test` step. This is a stale/conflicting PR, not a safe merge.
- Actual proposed bumps (from branch diffs at their merge-bases):
  - pip: `openai 1.x→2.52`, `pytest 8→9.1.1`, `pytest-asyncio 0.23→1.4`, `python-telegram-bot 22.0→22.8`, `python-dotenv 1.0.1→1.2.2`, `openpyxl 3.1.0→3.1.5`.
  - github-actions: `checkout 4→7`, `setup-node 4→7`, `setup-python 5→7`.
  - npm: `autoprefixer 10.4.20→10.5.4`, `oxlint 1.71→1.77`, `@types/node 24→26`, `vite 8.1.1→8.2.0`, `@vitejs/plugin-react 6.0.3→6.0.5`, `typescript 6→7`, `tailwindcss 3→4`, plus consolidated `react`/`react-dom`/`@types/react`/`@types/react-dom` patch bumps.
- Major/high-risk migrations requiring Claude review before merge: OpenAI 1→2, pytest 8→9, pytest-asyncio 0→1, Tailwind 3→4, TypeScript 6→7. These match the existing `GAP-019` entries.
- Recommended action: Dependabot should be allowed to rebase/refresh these branches onto current `main` before any are considered; none should be merged in their current stale state. The `checkout 4→7` branch in particular should be refreshed or closed.
- Status: **COMPLETED — triage recorded; no dependency merged.**

### VERIFY-010 — Recheck CI/action dependency state

- Priority: Medium
- Evidence: current `.github/workflows/ci.yml` still uses `actions/checkout@v4`, `actions/setup-python@v5`, and `actions/setup-node@v4`, while open Dependabot PRs propose newer major versions.
- Required result: determine whether each action PR is compatible with current CI and whether any PR is stale/conflicting.
- Status: **COMPLETED** — see VERIFY-009. All three action branches are 65 commits behind `main`. The `checkout 4→7` branch is a direct functional conflict with current CI (it would revert the Node 22 setting and delete the Unit tests step); `setup-node 4→7` and `setup-python 5→7` are stale but otherwise clean version bumps. None should be merged in their current state.

### VERIFY-011 — Screen-by-screen responsive Mini App audit

- Priority: High
- Owner: Claude/frontier for design changes; smaller model may perform bounded reproduction/measurement only
- Evidence: the UI/UX log explicitly records that the dedicated responsive audit was missed in Pass 4. Landing still uses an approximate `calc(100dvh - 8.5rem)` height.
- Required result: systematic narrow/short viewport audit before altering layout architecture.
- Status: **CLAUDE-LED audit; smaller model may gather measurements only.**

### VERIFY-012 — Recheck auth boundary when routes change

- Priority: Medium
- Evidence: `SECURITY_AUDIT_REPORT.md` identifies `_API_PATHS` as a security boundary and requires every new route to be added to the auth gate.
- Required result: every future route change must be reviewed against authentication and authorization expectations.
- Status: **ONGOING SECURITY CONTROL, not a one-off bug.**

### VERIFY-013 — Investigate importer archive-directory wiring

- Priority: Medium
- Owner: smaller review model first; Claude if semantics or architecture are unclear
- Evidence: `importer.py` exposes `ORIGINALS_DIR` and `IMPORTS_DIR` globals that are initialized to `None` and conditionally used. The audit report flagged this as potentially incomplete archival wiring.
- Required result: trace configuration, initialization, call sites, and actual runtime behavior to determine whether uploaded originals/imports are correctly archived.
- Constraint: investigation first; do not invent directory semantics or change persistence behavior.
- Escalation: if configuration ownership or archival semantics are unclear, stop with evidence for Claude/user.
- Status: **COMPLETED — FIXED**
- Notes: Investigation confirmed the archival feature was dead in production. `importer.py` defined its own module-level `ORIGINALS_DIR = None` / `IMPORTS_DIR = None` shadowing `config.py`'s real `Path`s, and nothing ever assigned the config values into the importer module globals (grep found no `importer.ORIGINALS_DIR =` anywhere). Every archival block (`import_image`, `import_xlsx`, `import_ai_text`) is guarded by `if ORIGINALS_DIR and ...`, so neither the original file nor the normalized JSON was ever saved at runtime, and `result.original_path`/`result.normalized_path` were always `None`. Tests passed only because `tests/test_importer.py` monkeypatches the globals. Fix: `importer.py` now imports the real paths via `from config import IMPORTS_DIR, ORIGINALS_DIR`, which binds the config `Path`s into the module namespace (keeps the existing monkeypatch-based tests working). Full suite: 388 passed.

### VERIFY-014 — Review API route/documentation parity

- Priority: Low
- Owner: smaller review model
- Evidence: `/queue/resume` exists in the current Mini App API but is not consistently represented in architecture/API documentation.
- Required result: compare implemented Mini App routes with documented routes and report concrete mismatches. Documentation changes may be delegated separately once verified.
- Status: **COMPLETED**
- Notes: The implemented route set (19 routes in `_API_PATHS`, `mini_app_api.py`) was compared with `ARCHITECTURE.md`. `POST /import` was the only mismatch — implemented and auth-gated but absent from the docs. It was added to the route list, and the `/export` admin-only / `/import` non-admin distinction was noted. All other implemented routes were already documented, including `POST /queue/resume`.

### VERIFY-015 — Review API auth-boundary coverage after route changes

- Priority: Medium
- Owner: smaller review model
- Evidence: authentication is implemented through an explicit API-path boundary. This is a recurring maintenance risk whenever endpoints are added.
- Required result: inspect the current route list against the auth gate and report any actual mismatch; do not redesign authentication.
- Status: **COMPLETED**
- Notes: Every path handled in `mini_app_api._api_request` is present in `_API_PATHS` (the auth gate), and every `_API_PATHS` entry has a handler — no mismatch. A parametrized regression test (`TestAuthBoundaryCoversAllRoutes`) now asserts every path in `_API_PATHS` returns 401 without credentials, locking the boundary to the literal route set.

## Findings: known product/architecture work that must not be delegated yet

### GAP-013 — Mini App import flow

Importing is still Telegram-side. A Mini App import workflow is a product/workflow feature and must be designed by Claude/user first. Smaller models may implement bounded pieces after the API/workflow contract exists.

### GAP-014 — Settings functionality

The Settings page still contains deliberately disabled placeholders for several categories, including Phone Handling, Display, Queue, Search, Language, Accent Color, Animation Intensity, and parts of Admin/Diagnostics. These are not bugs merely because they are disabled. Implementing them requires UX/product decisions; keep major work with Claude.

### GAP-015 — Pre-ready N-deep customers

The UI/UX log identifies this as the largest remaining Settings/backend capability gap. It requires defining the desired queue semantics before implementation. Claude/user first; smaller model only for subsequent bounded wiring/tests.

### GAP-016 — Paid write path

The real `Paid` workflow and whether it exists in Telegram, Mini App, or both remain product decisions. Do not delegate implementation before semantics are defined.

### GAP-017 — Fully blacklisted customer eligibility

The queue behavior for a customer whose every phone number is blacklisted remains a business-rule decision. Do not let a smaller model invent the rule.

### GAP-018 — Session timing semantics

Wall-clock versus idle-aware timing remains a product/statistics decision. Do not implement without an explicit choice.

### GAP-019 — Major dependency migrations

OpenAI v2, pytest 9, pytest-asyncio 1.x, Tailwind 4, and TypeScript 7 require Claude-level review because they cross API/configuration or tooling boundaries. Smaller models may later handle isolated follow-up fixes/tests after the migration design is established.

## Findings: documentation drift discovered during audit

### STATE-020 — UI testing documentation is now up-to-date

The repository now has Vitest, a dedicated `frontend/vitest.config.ts`, a `test` package script, CI's Unit tests step, and recent commits adding 22 frontend tests. The UI/UX log and the comment inside `vitest.config.ts` have been updated to reflect this.

### STATE-021 — Status snapshot must distinguish current CI from historical test counts

Recent history records backend counts of 330, 332, 334, 342, and 348 as successive milestones. These are historical verification results, not necessarily the current count. Future status updates should record the commit and exact current verification result together.

### STATE-022 — Open Dependabot work is not represented in project status

The previous delegation template contained no current GitHub PR inventory. The 18 open dependency PRs are now explicitly tracked here so they cannot be mistaken for unowned or nonexistent work.

### STATE-023 — API documentation drift: `/queue/resume`

The current API exposes `/queue/resume`, but architecture/API documentation does not consistently show it. This is a low-priority documentation-maintenance issue, not evidence that the endpoint itself is broken.

### STATE-024 — Paid terminology needs a single documented contract

The code/UI may use `Paid` while the actual product semantics remain unresolved. Keep the terminology mismatch visible, but do not allow a documentation fix to silently define what Paid is supposed to do.

## Findings: security posture

The security audit remains substantially resolved: Mini App Telegram auth, shared admin authorization, admin-gated export, restricted CORS, and denied-admin audit logging are implemented. The security document still correctly identifies three ongoing controls: new routes must join the auth boundary, the anonymous development escape hatch must never be enabled outside local testing, and future route growth must be checked for auth/authorization drift.

No new confirmed security vulnerability was established by this audit. The stale `_security_check.py` utility is a maintenance/documentation problem, not evidence of a current breach.

## Findings: GitHub work state

- Open Issues: none.
- Open PRs: 18, all Dependabot dependency/update PRs.
- No active non-Dependabot implementation PR was found during this audit.
- Major dependency PRs should not be merged solely because they are generated by Dependabot.
- PR #5 is explicitly open and unmerged; GitHub reports it as not mergeable in its current state, and it has no submitted reviews.

## Future improvements — low priority / not current blockers

These are intentionally separated from the actionable backlog. They are ideas or technical-quality improvements that could make the project stronger, but they should not distract Claude or smaller models from current product work. They only become active tasks after confirming that the benefit still outweighs the complexity.

### FUT-001 — Improve operational observability

- Priority: Low
- Potential value: make long-running bot failures, API errors, importer failures, queue anomalies, and restart events easier to diagnose.
- Possible direction: structured event logging and clearer correlation/session identifiers.
- Do not implement as a broad logging rewrite without measuring the current diagnostic gaps.

### FUT-002 — Add targeted performance baselines

- Priority: Low
- Potential value: establish simple measurements for customer search, queue operations, importer processing, API latency, and statistics generation before optimization becomes necessary.
- Trigger: only when real data or profiling shows a bottleneck.

### FUT-003 — Reduce responsibility concentration in large modules

- Priority: Low
- Potential value: modules such as the database/API layers may become easier to maintain if responsibilities grow further.
- Trigger: refactor only when a concrete maintenance problem exists; avoid splitting files merely to reduce line count.
- Owner: Claude/frontier for architecture; smaller models only for mechanical sub-refactors with explicit boundaries.

### FUT-004 — Consolidate duplicated status/outcome vocabulary

- Priority: Low
- Potential value: reduce the risk of Telegram, Mini App, database, statistics, and UI layers drifting into slightly different names for the same state.
- Trigger: revisit when another state/outcome feature is added.
- Owner: Claude first because this may affect business semantics.

### FUT-005 — Consolidate duplicated process-management logic

- Priority: Low
- Potential value: reduce divergence between launcher/process-management paths.
- Trigger: only if a concrete bug or maintenance burden is demonstrated.

### FUT-006 — Review automatic restart behavior

- Priority: Low
- Potential value: distinguish recoverable transient failures from failures that should stop the process and alert an operator.
- Trigger: after operational usage reveals restart loops or hidden failures.
- Owner: Claude/operations decision first.

### FUT-007 — Profile customer search at realistic scale

- Priority: Low
- Potential value: determine whether current search logic and indexing remain adequate as customer volume grows.
- Trigger: benchmark with representative data before changing queries or schema.

### FUT-008 — Expand backend coverage around operational modules

- Priority: Low
- Potential value: strengthen regression protection around importer, queue, statistics, and API integration boundaries.
- Constraint: add tests for defined behavior; do not use tests as a reason to invent new behavior.
- Smaller models can handle focused test additions once target behavior is explicit.

### FUT-009 — Review AI-provider timeout/failover behavior under real failures

- Priority: Low
- Potential value: ensure parser failover behaves predictably during timeout, rate-limit, malformed-response, and provider-outage scenarios.
- Trigger: reproduce or observe a real failure mode before changing retry/failover policy.
- Owner: Claude for policy; smaller model for bounded regression tests.

### FUT-010 — Harden local-development data handling before wider deployment

- Priority: Low now; potentially High before multi-user/bank deployment
- Potential value: improve encryption, secret handling, local database protection, backup/restore controls, and operational isolation before the system is used with materially sensitive production data.
- Trigger: deployment-readiness review.
- Owner: Claude/security architecture + user/IT policy; not a small-model design task.

### FUT-011 — Define deployment/operations model for multiple concurrent instances

- Priority: Low now; High before bank-wide deployment
- Potential value: establish process isolation, shared database strategy, job ownership, locking, configuration, secrets, backups, and observability for multiple simultaneous users/instances.
- Trigger: when moving from local/single-instance use toward shared server deployment.
- Owner: Claude + user/IT architecture.

### FUT-012 — Improve documentation generation/consistency checks

- Priority: Low
- Potential value: detect when endpoint lists, commands, test instructions, and status claims drift from code.
- Trigger: if documentation drift continues after the current cleanup.
- Smaller model may implement narrow checks once the desired source-of-truth rules are defined.

### FUT-013 — Establish a lightweight frontend accessibility regression checklist

- Priority: Low
- Potential value: protect touch targets, keyboard/focus behavior where relevant, labels, contrast, and error-state readability as the UI evolves.
- Owner: Claude defines the UX standard; smaller models can perform bounded checks.

### FUT-014 — Review frontend bundle/runtime performance

- Priority: Low
- Potential value: identify unnecessary dependencies, oversized assets, or expensive rendering once the UI stabilizes.
- Trigger: after the major UI pass, not during active redesign.

### FUT-015 — Add backup/restore verification procedures

- Priority: Low now; High before production deployment
- Potential value: ensure customer, queue, session, and statistics data can be recovered predictably.
- Trigger: before production or multi-user deployment.
- Owner: Claude/operations; smaller models can test a defined procedure.

## Verification-only queue

- Verify CORS has no wildcard fallback.
- Verify denied admin attempts remain audit-logged.
- Verify every real Mini App API endpoint is authenticated/authorized as required.
- Verify `bot.py` remains the single entrypoint when Mini App is enabled — confirmed 2026-08-10: `bot.py` `main()` calls `launch_mini_app_stack()` in-process; `start_mini_app.py` `launch_mini_app_stack()` does not launch the bot; only `start_mini_app.py` standalone `main()` spawns `bot.py --no-mini-app` as a subprocess (intentional separate mode). `Application.builder()` / `run_polling()` appear only in `bot.py`. 391 tests pass.
- Verify Mini App API remains a thin adapter over shared backend services.
- Verify frontend placeholders remain honest.
- Verify current Vitest tests and CI remain aligned.
- Verify documentation claims against live code after substantial passes.
- Triage open Dependabot PRs before assigning any dependency work — completed 2026-08-10 (VERIFY-009/010).
- Verify `bot.py` remains the single entrypoint when Mini App is enabled — verified 2026-08-10 (see note above).
- Verify importer archive-directory wiring (`VERIFY-013`).
- Verify route/documentation parity (`VERIFY-014`) — completed 2026-08-10.
- Verify auth-boundary coverage after API route changes (`VERIFY-015`) — completed 2026-08-10.

## Escalation rules

A smaller model must stop and report when it encounters a product decision, security-sensitive design choice, schema migration, unspecified API contract change, queue/customer-state semantic change, broad UI redesign, framework-selection decision, unrelated failing test, or any requirement outside its explicit task scope.

The correct response to an escalation is evidence, not improvisation.

## Completion protocol

A delegated task is complete only when scope remained bounded, required checks pass, the diff was reviewed, no runtime/generated/secrets were introduced, the commit is focused, and the resulting GitHub state is independently verified. New follow-up findings become separate records rather than silently expanding the completed task.

## Recently completed / already handled

- CORS wildcard replaced with an allowlist; 8 tests added.
- Denied admin actions now produce `admin_action_denied`; 7 tests added.
- Real Home/Landing screen split from calling workflow.
- Dead Call Again/Note controls removed/replaced.
- Pause/Resume and real Export wired into Mini App Commands.
- SessionComplete Export fixed.
- CustomerCard index label and phone-number display fixed.
- Max Call Attempts and Auto Advance became real backend-enforced settings.
- Frontend Vitest test runner and 22 initial tests were added; CI now runs Unit tests.
- CI Node was raised from 20 to 22 after jsdom's actual runtime requirement was discovered.
- Repository stabilization/setup/doctor tooling was completed and fresh-clone behavior verified.
- CORS and denied-admin security fixes were completed and documented.
- `/import` documented in the API contract (VERIFY-014); read-only xlsx workbook now closed, fixing Windows temp-file cleanup in the Mini App `/import` path; auth-boundary coverage regression test added (VERIFY-015).

## Decisions still needed

- Paid write path and interface(s).
- Fully blacklisted customer queue eligibility.
- Wall-clock versus idle-aware session timing.
- Exact Settings feature priorities/semantics.
- Whether and how the Mini App should gain its own import workflow.
- Whether major dependency upgrades are worth the migration cost.

## Current recommended next actions

1. DLG-005 through DLG-010 (small cleanup/documentation) — completed.
2. VERIFY-009/010 (Dependabot PR triage) — completed. All 18 branches are stale; none should be merged without a Dependabot rebase.
3. VERIFY-013 through VERIFY-015 (bounded audits) — completed.
4. Have Claude perform the dedicated responsive UI audit and decide the next Settings/UI pass.
5. Keep product decisions above out of the smaller-model queue until explicitly resolved.
6. Treat FUT-001 through FUT-015 as a low-priority improvement reservoir, not active work, unless a trigger makes one relevant.
7. After the next Claude pass, run a fresh repository-wide delegation audit and reconcile this file against the new HEAD.

## Delegation audit metadata

- Audit date: 2026-08-09
- Audited HEAD: `9f89cf9619f8d454268a3e18a88a2cdca5a5b313`
- Last control-center template update: 2026-08-09
- Current repository has 18 open Dependabot PRs and no open Issues.
- Known stale documentation found: UI/UX testing gap, Vitest config comment, and API route/documentation parity around `/queue/resume`.
- Known stale repository artifacts found: `_security_check.py`, `_install_err.log`.
- New verified delegation candidates added after independent review of an external AI audit: DLG-009, DLG-010, VERIFY-013, VERIFY-014, VERIFY-015.
- VERIFY-014 (route/documentation parity) and VERIFY-015 (auth-boundary coverage) were verified and completed on 2026-08-10; `POST /import` was added to `ARCHITECTURE.md`, a 19-route auth-boundary regression test was added, and a Windows xlsx temp-file cleanup bug in the `/import` path was fixed.
- Low-priority future-improvement reservoir added after independent review: FUT-001 through FUT-015.
- Next full audit trigger: after the next substantial Claude pass, dependency migration, or architecture change.
