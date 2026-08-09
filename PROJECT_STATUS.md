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
- Status: **READY TO DELEGATE**.

### DLG-006 — Remove empty `_install_err.log` artifact

- Priority: Low
- Owner: smaller coding model
- File: `_install_err.log`
- Evidence: the tracked file is empty and is a generated-looking root-level log artifact. `AGENTS.md` says generated/runtime artifacts must not be committed.
- Required result: delete it and confirm no workflow depends on it.
- Verification: repository search for references; diff review.
- Status: **READY TO DELEGATE**.

### DLG-007 — Correct stale frontend-testing documentation

- Priority: Medium
- Owner: smaller documentation model
- Files: `PROJECT_STATUS.md`, `FreikerDialBot_UI_UX_Development_Log.md`, `frontend/vitest.config.ts`
- Evidence: `frontend/package.json` has `"test": "vitest run"`; `vitest.config.ts` exists; the repository contains Vitest tests; CI runs `npm run test`. However, the UI/UX log still says no frontend test runner exists, and the Vitest config comment still describes the gap as if it were unresolved.
- Required result: update documentation/comments to state that Vitest is now installed and CI-covered, while accurately describing the current coverage limitations.
- Constraint: do not expand test architecture or add broad tests.
- Verification: compare docs with `package.json`, `vitest.config.ts`, CI, and actual test files.
- Status: **READY TO DELEGATE**.

### DLG-008 — Correct README frontend-validation instructions

- Priority: Low
- Owner: smaller documentation model
- File: `README.md`
- Evidence: README's frontend-only validation example currently lists `npm ci`, typecheck, and build but omits `npm run test`, while `AGENTS.md` and CI require the Vitest test step.
- Required result: add the current frontend test command without duplicating the full validation policy.
- Status: **READY TO DELEGATE**.

## Findings: verification / audit work

### VERIFY-009 — Triage all open Dependabot PRs

- Priority: High
- Owner: smaller review model for mechanical triage; Claude for major migrations
- Current state: 18 open Dependabot PRs exist.
- Safe/minor candidates to review first: #1 setup-python 5→7, #2 setup-node 4→7, #3 python-telegram-bot 22.8, #4 checkout 4→7, #6 openpyxl, #8 Vite 8.1.4→8.2.0, #9 python-dotenv, #13 oxlint, #14 react-dom patch, #15 React patch, #16 plugin-react patch, #17 @types/node, #18 autoprefixer.
- Major/high-risk migrations requiring Claude review before merge: #5 OpenAI 1→2, #7 pytest 8→9, #10 pytest-asyncio 0→1, #11 Tailwind 3→4, #12 TypeScript 6→7.
- Important evidence: PR #5 changes only the OpenAI version constraint; `ai_parser.py` uses `AsyncOpenAI`, `RateLimitError`, `APIError`, and `chat.completions.create`, so the migration requires actual test/review rather than assuming a dependency-only change is safe. PR #11 is a Tailwind major migration and removes the Tailwind 3 dependency tree while the current repo still has a Tailwind 3-style `tailwind.config.js` and `postcss.config.js`; it is not a mechanical merge.
- No review submissions were found on the inspected major PRs #5, #11, and #12.
- Status: **READY AS A VERIFICATION/REVIEW TASK; do not blindly merge dependency PRs.**

### VERIFY-010 — Recheck CI/action dependency state

- Priority: Medium
- Evidence: current `.github/workflows/ci.yml` still uses `actions/checkout@v4`, `actions/setup-python@v5`, and `actions/setup-node@v4`, while open Dependabot PRs propose newer major versions.
- Required result: determine whether each action PR is compatible with current CI and whether any PR is stale/conflicting.
- Status: **READY TO DELEGATE as review only.**

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

### STATE-020 — UI testing documentation is stale

The repository now has Vitest, a dedicated `frontend/vitest.config.ts`, a `test` package script, CI's Unit tests step, and recent commits adding 22 frontend tests. The UI/UX log and the comment inside `vitest.config.ts` still describe the frontend test runner as absent. This must be corrected so future agents do not make a duplicate test-runner task.

### STATE-021 — Status snapshot must distinguish current CI from historical test counts

Recent history records backend counts of 330, 332, 334, 342, and 348 as successive milestones. These are historical verification results, not necessarily the current count. Future status updates should record the commit and exact current verification result together.

### STATE-022 — Open Dependabot work is not represented in project status

The previous delegation template contained no current GitHub PR inventory. The 18 open dependency PRs are now explicitly tracked here so they cannot be mistaken for unowned or nonexistent work.

## Findings: security posture

The security audit remains substantially resolved: Mini App Telegram auth, shared admin authorization, admin-gated export, restricted CORS, and denied-admin audit logging are implemented. The security document still correctly identifies three ongoing controls: new routes must join the auth boundary, the anonymous development escape hatch must never be enabled outside local testing, and future route growth must be checked for auth/authorization drift.

No new confirmed security vulnerability was established by this audit. The stale `_security_check.py` utility is a maintenance/documentation problem, not evidence of a current breach.

## Findings: GitHub work state

- Open Issues: none.
- Open PRs: 18, all Dependabot dependency/update PRs.
- No active non-Dependabot implementation PR was found during this audit.
- Major dependency PRs should not be merged solely because they are generated by Dependabot.
- PR #5 is explicitly open and unmerged; GitHub reports it as not mergeable in its current state, and it has no submitted reviews.

## Verification-only queue

- Verify CORS has no wildcard fallback.
- Verify denied admin attempts remain audit-logged.
- Verify every real Mini App API endpoint is authenticated/authorized as required.
- Verify `bot.py` remains the single entrypoint when Mini App is enabled.
- Verify Mini App API remains a thin adapter over shared backend services.
- Verify frontend placeholders remain honest.
- Verify current Vitest tests and CI remain aligned.
- Verify documentation claims against live code after substantial passes.
- Triage open Dependabot PRs before assigning any dependency work.

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

## Decisions still needed

- Paid write path and interface(s).
- Fully blacklisted customer queue eligibility.
- Wall-clock versus idle-aware session timing.
- Exact Settings feature priorities/semantics.
- Whether and how the Mini App should gain its own import workflow.
- Whether major dependency upgrades are worth the migration cost.

## Current recommended next actions

1. Delegate DLG-005 through DLG-008 as small cleanup/documentation tasks.
2. Have a smaller model perform VERIFY-009/010 dependency-PR triage without merging major migrations.
3. Have Claude perform the dedicated responsive UI audit and decide the next Settings/UI pass.
4. Keep product decisions above out of the smaller-model queue until explicitly resolved.
5. After the next Claude pass, run a fresh repository-wide delegation audit and reconcile this file against the new HEAD.

## Delegation audit metadata

- Audit date: 2026-08-09
- Audited HEAD: `9f89cf9619f8d454268a3e18a88a2cdca5a5b313`
- Last control-center template update: 2026-08-09
- Current repository has 18 open Dependabot PRs and no open Issues.
- Known stale documentation found: UI/UX testing gap and Vitest config comment.
- Known stale repository artifacts found: `_security_check.py`, `_install_err.log`.
- Next full audit trigger: after the next substantial Claude pass, dependency migration, or architecture change.
