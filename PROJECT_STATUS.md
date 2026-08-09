# PROJECT_STATUS.md

Current snapshot of the repository as of the current main tree.

For rules and working conventions, read `AGENTS.md`.
For technical architecture and endpoint details, read `ARCHITECTURE.md`.
For security findings, read `SECURITY_AUDIT_REPORT.md`.
For user-facing overview and setup, read `README.md`.
For frontend UI/UX pass history and the current design backlog, read `FreikerDialBot_UI_UX_Development_Log.md`.

## What is already in the repo

- Shared backend wiring exists in `backend.py`.
- The Telegram bot, queue, session, statistics, importer, and Mini App API all share the same core data model.
- The importer pipeline covers screenshots, pasted text, JSON, and spreadsheet input.
- The queue supports deterministic next-customer selection, editing, blacklists, search, history, and admin actions.
- The Mini App frontend is a real React/TypeScript/Vite app, not a stub.
- Telegram Mini App authentication and admin authorization logic are implemented in the repo.
- The repository docs are centered on `AGENTS.md`, `PROJECT_STATUS.md`, `ARCHITECTURE.md`, `SECURITY_AUDIT_REPORT.md`, and `README.md`.

## What was folded into this file from older docs

- The old backlog file is now represented here as the open-issues list below.
- The old setup-after-Claude notes are now represented here as the security/setup recap below.
- The old delegation/task notes were removed as a separate file and folded back into this file as the reusable delegation control center below.

## Security and setup recap

- The data-history remediation decision is already completed and should stay treated as a completed decision, not a live task.
- Mini App auth is mandatory by default on real endpoints.
- `bot.py` is the single entry point for the stack when the Mini App is enabled.
- The launcher flag typo was fixed in the earlier setup pass.
- The dependabot configuration exists and should stay on the repo maintenance path.
- The Mini App API is still the thin adapter around the shared backend services, not a separate backend.

# Delegation Control Center

This section is the operational control layer for bounded work that can be delegated to smaller, older, weaker, or less capable coding/review models. It is intentionally kept inside the canonical `PROJECT_STATUS.md`; do not create a separate delegation Markdown file.

## Purpose and authority

The Delegation Control Center tracks:

- who is currently working on what;
- work already being handled by Claude/frontier-level models;
- work that is safe to hand to a smaller model;
- implementation gaps discovered during audits;
- verification-only work;
- blocked or decision-dependent work;
- delegation status, acceptance criteria, and verification evidence;
- what should happen next.

Repository code is authoritative. Documentation describes intent, but live code and tests determine fact. If this section conflicts with the repository, update this section rather than trusting the stale entry.

This section is not a replacement for the other canonical documents:

- `AGENTS.md` owns agent rules, workflow, validation, commit cadence, and documentation policy.
- `PROJECT_STATUS.md` owns current state, delegation, open work, decisions, and completion recaps.
- `ARCHITECTURE.md` owns architecture, module boundaries, API contracts, and ownership rules.
- `SECURITY_AUDIT_REPORT.md` owns security findings and security posture.
- `README.md` owns user-facing setup and overview.
- `FreikerDialBot_UI_UX_Development_Log.md` owns detailed UI/UX pass history and UI design backlog.

## Model responsibility rules

The Delegation Handler should default to the smallest model capable of completing the task safely.

### Claude / frontier model / user decision territory

Do not delegate these to weaker models unless the task has already been reduced to a completely mechanical subtask with explicit acceptance criteria:

- major UI/UX redesigns;
- complete screen redesigns or new visual systems;
- large frontend feature work;
- major backend features;
- new product workflows;
- architecture changes;
- changes to shared service boundaries;
- database/schema redesigns or migrations with broad consequences;
- security architecture or authentication redesign;
- changes to core queue semantics;
- changes to customer-state ownership;
- complex importer/prompt redesigns;
- cross-cutting features spanning multiple subsystems;
- product decisions or ambiguous requirements;
- decisions that change existing user-facing behavior materially;
- resolving conflicts between existing architectural rules;
- large refactors where the correct target architecture must be decided first.

The weaker model may verify, test, document, or make a small isolated follow-up after Claude has established the design.

### Smaller-model territory

These are the default delegation candidates when scope and acceptance criteria are clear:

- small isolated bug fixes;
- focused regression tests;
- small test additions for already-defined behavior;
- verification of an existing endpoint or feature;
- documentation corrections that follow live code;
- mechanical documentation updates;
- small deterministic refactors that do not alter architecture;
- removal of clearly unused code/imports when verified safe;
- small validation improvements with existing rules;
- narrow dependency/configuration audits;
- CI checks or small maintenance changes with clear expected behavior;
- checking that an existing feature actually works;
- reproducing and documenting a suspected bug;
- small logging/audit improvements with an already-defined event model;
- bounded backend maintenance;
- bounded Telegram UI maintenance;
- bounded Mini App API maintenance;
- bounded frontend maintenance that does not redesign the UI system.

The default rule is: **delegate implementation complexity, not decision-making.**

## Current work ownership

| Area | Default/Current owner | Delegation rule | Source of truth |
|---|---|---|---|
| Major UI/UX system and redesign | Claude/frontier | Do not duplicate with smaller model | `FreikerDialBot_UI_UX_Development_Log.md` |
| Large Mini App features | Claude/frontier | Do not duplicate | `ARCHITECTURE.md`, UI/UX log |
| Major backend features | Claude/frontier | Do not duplicate | `ARCHITECTURE.md`, this file |
| Architecture/security decisions | Claude + user | Decision required before delegation | `ARCHITECTURE.md`, `SECURITY_AUDIT_REPORT.md` |
| Product behavior decisions | User + Claude | Never infer | Decision section below |
| Small bounded implementation | Delegation Handler → smaller AI | Delegate when acceptance criteria are explicit | This section |
| Verification/audit work | Delegation Handler → smaller AI | Preferred use of weaker models | Verification queue below |
| Project-wide status tracking | Delegation Handler | Keep this section current | This section |

## Delegation state machine

Every delegated item should move through these states:

`DISCOVERED → ASSESSED → READY TO DELEGATE → DELEGATED → IMPLEMENTED → VERIFIED → COMPLETED`

Other valid states are:

- `BLOCKED` — cannot proceed without another change or decision.
- `ESCALATED` — smaller model found a larger problem and stopped.
- `DEFERRED` — intentionally postponed.
- `SUPERSEDED` — replaced by another task or design.
- `ALREADY HANDLED` — another model/pass has already resolved it.

Never mark an item `COMPLETED` merely because an AI says it is finished. Verification evidence is required.

## Active delegations

No smaller-model delegation is currently recorded as active in this snapshot. Add an entry here when work is actually handed to another model.

### Delegation record template

```text
DLG-XXX — Short task name
Status: DELEGATED
Owner: [model/agent]
Model class: [small / medium / Claude / human]
Started: [date]
Parent finding: [GAP/BUG/VERIFY ID]

Problem:
[exact problem]

Scope:
[exact files/components]

Allowed files:
[list]

Files that must not be changed:
[list]

Required result:
[observable result]

Acceptance criteria:
[checklist]

Verification:
[exact commands/tests/manual checks]

Dependencies:
[list]

Escalation condition:
[when the model must stop]

Commit/PR:
[after completion]

Last verified:
[date + evidence]

Notes:
[short durable notes]
```

## Ready-to-delegate queue

These are bounded tasks that do not require a new product or architectural decision before implementation.

### DLG-CANDIDATE-001 — Restrict CORS to the real Mini App origin

- Priority: High
- Difficulty: Small
- Recommended model: smaller coding model
- Problem: Mini App responses previously exposed `Access-Control-Allow-Origin: *`; the current security cleanup added the configured allowlist, but this item should only be considered active if live code/audit shows any remaining wildcard path.
- Scope: `mini_app_api.py` and focused tests only.
- Required result: configured Mini App origin is used; local development remains functional; no wildcard fallback remains on real API responses.
- Verification: targeted CORS tests plus full backend test suite.
- Status: **RECHECK BEFORE DELEGATING** — the current status recap says this security item was already completed. Do not duplicate it without verifying the live code.

### DLG-CANDIDATE-002 — Audit-log denied admin attempts

- Priority: High
- Difficulty: Small
- Recommended model: smaller coding model
- Problem: this was previously identified as a missing denial audit event.
- Scope: `admin_commands.py`, `mini_app_api.py`, and focused tests only.
- Required result: denied Telegram admin actions and denied Mini App export attempts produce the defined `admin_action_denied` event without changing successful-action logging.
- Verification: targeted denial tests plus full backend suite.
- Status: **RECHECK BEFORE DELEGATING** — the current status recap says this item was already completed. Do not duplicate it without verifying the live code.

### DLG-CANDIDATE-003 — Focused regression-test maintenance

- Priority: Medium
- Difficulty: Small
- Recommended model: smaller coding model
- Scope: tests only unless a test reveals a clearly isolated defect.
- Goal: add regression coverage for an already-defined behavior where the missing test is obvious and no framework/product decision is required.
- Stop condition: if coverage requires selecting a new frontend test framework, redesigning test architecture, or changing behavior, escalate to Claude/user.
- Verification: relevant tests plus required full-suite checks from `AGENTS.md`.
- Status: Ready only when a specific missing regression is identified.

### DLG-CANDIDATE-004 — Documentation/code consistency checks

- Priority: Low/Medium
- Difficulty: Small
- Recommended model: smaller review model
- Scope: canonical Markdown files only.
- Goal: compare documented routes/features/status against live code and identify factual drift.
- Constraint: do not invent intended behavior; report contradictions for the Delegation Handler to classify.
- Verification: every correction must be grounded in the current repository.
- Status: Ready as an audit task.

## Discovered gaps / unassigned work

These are known or potentially known issues that are **not automatically delegation candidates**. They must be classified before implementation.

### GAP-001 — Mini App import flow

- Current state: importing remains Telegram-only.
- Classification: feature gap.
- Likely owner: Claude/frontier if a new Mini App workflow is required.
- Reason: this is a product/workflow feature, not a small maintenance task.
- Smaller AI role: only bounded implementation after the workflow/API design is established.

### GAP-002 — Frontend automated testing

- Current state: frontend test coverage is sparse/absent and there is no frontend test runner configured in the current status snapshot.
- Classification: tooling/architecture decision.
- Likely owner: Claude + user decision first.
- Reason: selecting and integrating a frontend test framework is broader than a simple test addition.
- Smaller AI role: later, once the framework and test conventions are established, individual test cases can be delegated.

### GAP-003 — Settings placeholders

- Current state: `Settings.tsx` still contains honest disabled placeholders for Phone Handling, Display, Queue, Search, Language, Accent Color, Animation Intensity, and Version Info.
- Classification: feature/UI work.
- Likely owner: Claude/frontier for the actual UX/system design.
- Smaller AI role: only after the behavior and UI contract are defined; then individual wiring tasks may be delegated.

### GAP-004 — Landing full-screen sizing

- Current state: Landing uses `calc(100dvh - 8.5rem)`, which is an approximation rather than a measurement of actual rendered app-bar/bottom-nav dimensions on real devices.
- Classification: bounded UI maintenance, but may require device-specific validation.
- Likely owner: smaller AI for investigation/verification; Claude only if the fix requires a broader layout redesign.
- Next action: reproduce on representative mobile/Telegram WebView environments before changing the layout system.

### GAP-005 — Paid write path

- Current state: no final workflow decision.
- Classification: product decision.
- Owner: user + Claude.
- Smaller AI: not eligible until the write semantics are explicitly defined.

### GAP-006 — Fully blacklisted customer queue eligibility

- Current state: behavior requires a deliberate product rule.
- Classification: product/business-rule decision.
- Owner: user + Claude.
- Smaller AI: not eligible until the rule is chosen.

### GAP-007 — Session timing model

- Current state: decision remains between wall-clock timing and idle-aware timing.
- Classification: product/statistics decision.
- Owner: user + Claude.
- Smaller AI: not eligible until the desired semantics are chosen.

## Verification-only queue

Verification tasks are preferred delegation work when implementation is unnecessary.

- VERIFY-001 — Confirm current CORS behavior matches configured allowed origins and has no wildcard fallback.
- VERIFY-002 — Confirm denied admin attempts are audit-logged under the intended event type.
- VERIFY-003 — Confirm every real Mini App API route still requires Telegram authentication/admin authorization where required.
- VERIFY-004 — Confirm `bot.py` remains the single entry point when the Mini App is enabled.
- VERIFY-005 — Confirm Mini App API remains a thin adapter and does not duplicate queue/session/statistics business logic.
- VERIFY-006 — Confirm current frontend placeholder controls remain honest and do not imply unsupported functionality.
- VERIFY-007 — Re-run backend tests and frontend typecheck/build after a Claude UI or architecture pass and record the exact results.
- VERIFY-008 — Check documentation claims against live code after a significant implementation pass.

A verification model must not turn an audit finding into an unapproved feature implementation. If it finds a defect, report it with evidence and escalate/classify it.

## Deferred / blocked / decision-dependent work

Do not place these into the smaller-model implementation queue until the required decision is made:

- Paid write path and whether it exists in Telegram, Mini App, or both.
- Treatment of customers whose every phone number is blacklisted.
- Wall-clock versus idle-aware session timing.
- Frontend test-framework selection and testing architecture.
- Any major Mini App import workflow design.
- Any major UI redesign or new visual system.
- Any new shared backend architecture.

## Escalation rules for smaller models

A smaller model must stop and report rather than expanding scope when it encounters:

- a product decision not explicitly stated in the task;
- conflicting requirements;
- a security-sensitive design choice;
- a database/schema migration requirement;
- an API contract change not explicitly specified;
- a change to queue/customer-state semantics;
- architecture spanning multiple major modules;
- a broad UI/UX redesign;
- a need to select a new framework/tooling architecture;
- a failing test that indicates a deeper unrelated defect;
- an unexpected dependency on a component outside the allowed scope;
- acceptance criteria that cannot be determined from the task;
- a request to modify files marked forbidden by the delegation record.

The correct response to an escalation is evidence, not improvisation.

## Completion and verification protocol

A delegation is complete only when all applicable conditions are satisfied:

1. Scope remained bounded.
2. Required files were the only files changed, unless an explicitly justified dependency was necessary.
3. Tests/checks required by the task pass.
4. The broader required validation from `AGENTS.md` has been run when applicable.
5. The diff was reviewed.
6. No secrets/runtime/generated files were introduced.
7. The commit is small and focused.
8. The resulting commit is verified on GitHub rather than trusting only a local push result.
9. Any newly discovered follow-up work is recorded as a separate finding rather than silently expanding the completed task.
10. The delegation record is updated with the commit/PR and verification evidence.

## Delegation history

Keep completed delegation records compact. Preserve the durable facts needed to understand what happened and avoid repeating work.

```text
DLG-XXX
Task:
Owner/model:
Result: COMPLETED / ESCALATED / SUPERSEDED
Commit/PR:
Verification:
Follow-up findings:
Date:
```

## Current recommended delegation strategy

1. Prefer verification and small isolated maintenance work for weaker models.
2. Do not duplicate Claude's active UI/UX or major feature work.
3. Before delegating any item, verify that the current code has not already resolved it.
4. Give the smaller model a narrow prompt derived from a delegation record in this section.
5. Require explicit acceptance criteria and verification.
6. Escalate decisions rather than letting a weaker model invent behavior.
7. After the smaller model finishes, independently verify the result and update this section.
8. Keep this section current enough that a new AI can understand ownership and avoid duplicate work without needing the entire conversation history.

## Delegation audit metadata

- Last delegation-control update: 2026-08-09
- Repository: `Justin-Lemonade/FreikerDialBot-Automation`
- Branch: `main`
- Documentation authority: `AGENTS.md` + live repository code
- Current delegation section was rebuilt from the existing `PROJECT_STATUS.md`, `AGENTS.md`, and `ARCHITECTURE.md`.
- Known stale-risk: entries marked **RECHECK BEFORE DELEGATING** must be verified against live code before assignment.
- Next full delegation audit: after the next substantial Claude pass or when the repository state changes materially.

## What is currently open

- The Mini App still has no import flow of its own; importing remains Telegram-only.
- Frontend test coverage is still sparse or absent -- there is no frontend test runner configured yet (no vitest/jest). All frontend changes are validated by typecheck + lint + build + manual diff review, not automated frontend tests. Setting up a frontend test framework is its own decision, flagged as the top open item in `FreikerDialBot_UI_UX_Development_Log.md`.
- Settings > Phone Handling (primary-number preference, quick switching), Display, Queue (pre-ready count, active-queue/new-contacts ordering), most of Search, Language (Russian/Tajik), Accent Color, Animation Intensity, and Version Info are still unimplemented placeholders in `Settings.tsx` (honestly disabled, not faked) -- see the Settings section list there for the full current set.
- Landing's "full-screen" height (`calc(100dvh - 8.5rem)`) is an approximation of the app bar + bottom nav height, not measured against the actual rendered DOM on a real device.

## Recently completed

- **Security backlog cleanup:**
  - CORS: `Access-Control-Allow-Origin: *` replaced with a real allowlist (`Settings.mini_app_allowed_origins` -- the configured `mini_app_url`, the Vite dev server, plus an optional `MINI_APP_EXTRA_ALLOWED_ORIGINS` env var). 8 new tests.
  - Denied admin attempts (reset/clear/summary/export on Telegram, `/export` on the Mini App) are now audit-logged under a new `admin_action_denied` event_type, not just successful ones. 7 new tests.
  - Full suite: 348 passed.

- **UI pass 4 (multi-commit) -- see `FreikerDialBot_UI_UX_Development_Log.md` for the full self-review:**
  - Restored a real Home/Landing screen (`Landing.tsx`) separate from the live calling workflow. `Home.tsx` had literally documented itself as *being* the calling workflow, which directly contradicted the product intent -- `Screen` now has both `'home'` (Landing: Welcome Back, queue summary, Continue Session/Upload Contacts, Search/Commands/Settings shortcuts) and `'calling'` (the former merged screen).
  - Found and fixed real dead buttons via independent review: `OutcomeButtons`' secondary "Call Again" and "Note" buttons called outcome values (`call_again`, `note`) that `mini_app_api._map_outcome()` has no mapping for -- every tap returned a backend error. Replaced "Call Again" with a real "More Info" action (moved off the customer card, now sits below the primary outcome buttons) and removed the redundant broken "Note" button. Separately found `SessionComplete`'s Export button had no `onClick` at all; wired it to the same real `GET /export` `Commands.tsx` uses, via a new shared `lib/download.ts` helper.
  - `Commands.tsx`: Pause Queue and Export Data were both left disabled despite full backend support. Added `POST /queue/resume` (paired with `isPaused` on `/session/current`) so Pause/Resume is a real toggle; Export downloads the real file via the admin-gated `GET /export`. Added a real typed command input (help, stats, notes, search, pause, resume, export) mapped entirely to existing routes/screens -- no invented backend surface.
  - Bottom nav: label font 8px→10px, icon 18px→24px, real selected-state highlight (background + border + `aria-current`), touch target 52px→58px.
  - `CustomerCard`: fixed a genuinely dead `indexLabel` prop (declared, never passed by any caller) by wiring it to real session data.
  - `Settings.tsx`: Max Call Attempts and Auto Advance controls were below the ~44px mobile touch-target minimum (32px); both fixed.
  - Backend: 3 new tests (`/queue/resume`, `isPaused`). Full suite: 334 passed throughout every commit. Frontend typecheck, lint, and build all pass after every commit; every commit individually verified on GitHub via the API.

- **UI pass 3 (multi-commit):**
  - Fixed the Call button silently failing to dial on some mobile browsers/WebViews (including Telegram's): `onStartCall` was awaiting the `/call/start` bookkeeping request *before* navigating to `tel:`, which pushes the navigation past the click event's synchronous call stack -- several mobile browsers require `tel:`/`mailto:` navigation to happen within the original user-gesture event or they silently block it. Now dials first, synchronously, then fires bookkeeping afterward without awaiting it.
  - `mini_app_api._customer_payload` now returns `phones: [{number, isBlacklisted}]` for every number on file (previously collapsed to a single first-non-blacklisted `phone` string, which is kept for backward compatibility). `CustomerCard` (the live Home workflow card) and `CustomerDetail` both show every number as its own tap-to-dial link.
  - `CustomerCard` gained a "MORE INFO" button so `CustomerDetail` is reachable from the live call workflow, not only via Search. `CustomerDetail` now takes a `backLabel`/dynamic `onBack` so it returns to whichever screen opened it.
  - `ProgressHeader` compacted to a single thin row (count + segments + percent); dropped the "CUSTOMER PROGRESS" label row and the derived "~X REMAINING" estimate line (never a real backend value). `MainLayout` now only renders it on Home/calling-related screens (`home`, `complete`), not on Search/Commands/Statistics.
  - Fixed the customer-card slide animation clipping its own notched corners mid-transition: `<main>` (`overflow-y: auto`) was implicitly getting `overflow-x: auto` per the CSS overflow spec, hard-clipping the card as it translated 140% off-screen. Made `overflow-x: hidden` explicit and shortened the slide distance with an earlier opacity fade.
  - Search is now keyboard-safe on mobile (`inputMode="search"`, `enterKeyHint="search"`, autocomplete/autocorrect disabled, scrolls the input into view on focus so results aren't hidden behind the keyboard) and highlights the matched substring in each result's name/loan number/phone, computed client-side with the same case-insensitive substring test `Database.search_customers` actually uses.
  - `Settings.tsx` rebuilt into the UI pass 3 brief's categories (Calling Behavior, Phone Handling, Display, Queue, Search, Appearance, Language, Admin/Diagnostics). Added two more real rows: Backend Connectivity and Sync Status, now read from `useSession`'s `isStale`/new `lastSyncedAt` field instead of a decorative indicator. Every other row in each category is an honest, disabled placeholder labeled with what it will do, grouped correctly so wiring the real control later doesn't require reworking the screen.
  - Added the commit/push cadence rule to `AGENTS.md`.
  - Backend: 4 new tests (2 for the `phones` field, unrelated Max Call Attempts/Settings tests from the prior pass unaffected). Full suite: 332 passed throughout. Frontend typecheck, lint, and build all pass after every commit.

- **Max Call Attempts** is now a real, backend-enforced setting rather than a placeholder: `customers.attempt_count` tracks how many times a customer has been marked "Didn't Answer" (`QueueEngine.apply_action`), and `QueueEngine.restart_call_later` ("Call Back") excludes customers who have reached the configured cap instead of requeuing them forever. Configured via `GET/POST /settings` (generic `app_settings` key/value table -- see `database.py`), wired into `Settings.tsx` via `useAppSettings.ts`.
- **Auto Advance** is real: when off, completing an outcome no longer immediately swaps in the next customer -- the card stays frozen on the just-completed customer until the operator taps "Next Customer" (`App.tsx`'s `pendingAdvance` state). The backend already returned the next customer in the same response either way; this only changes when the frontend displays it.

## Decisions still needed

These are product decisions, not simple bugs:

- The real `Paid` write path and whether it should exist in both Telegram and the Mini App.
- What should happen to customers whose every phone number is blacklisted.
- Whether session duration should stay as wall-clock time or become idle-aware.

## User-facing prompts / options

If the next pass is meant to answer open product questions, the shortest choices are:

- **Paid:** add a real write path now, or keep it disabled until the workflow is defined.
- **Blacklist-by-phone:** keep it separate from customer-level blacklisting, or redefine queue eligibility to treat fully blacklisted customers as uncallable.
- **Session timing:** keep the current wall-clock measurement, or move to an idle-aware model.

## What to check next

1. Re-run the backend test suite.
2. Run the frontend typecheck and build.
3. Pick the next item from the open list above.
4. Keep future documentation inside the canonical Markdown files unless a tool explicitly requires another filename.
