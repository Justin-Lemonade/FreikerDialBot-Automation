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
- The old delegation/task notes were removed as a separate file and folded back into this file as a reusable delegation section.

## Security and setup recap

- The data-history remediation decision is already completed and should stay treated as a completed decision, not a live task.
- Mini App auth is mandatory by default on real endpoints.
- `bot.py` is the single entry point for the stack when the Mini App is enabled.
- The launcher flag typo was fixed in the earlier setup pass.
- The dependabot configuration exists and should stay on the repo maintenance path.
- The Mini App API is still the thin adapter around the shared backend services, not a separate backend.

## Delegated work / ready-to-delegate tasks

Use this section for bounded implementation specs that can be handed to a weaker model without losing context.

What belongs here:
- tasks with a clear scope and a clear stop condition;
- work that can be verified with tests, builds, or a diff review;
- implementation tasks that do not require a product decision first;
- task specs that would otherwise get lost in a separate Markdown file.

How to use it:
- keep each item short and specific;
- name the preferred model when delegation matters;
- list the files that may change and the files that must not change;
- state the exact outcome expected;
- include the verification command or test that must pass;
- move anything that needs product judgment, security judgment, or architectural redesign into `PROJECT_STATUS.md`'s decision or open-issues sections instead.

### Ready to delegate

#### 1. Restrict CORS to the real Mini App origin

- Why: `Access-Control-Allow-Origin: *` is still wide open on Mini App responses.
- Scope: `mini_app_api.py` only, plus focused tests.
- Goal: use the resolved Mini App origin instead of `*` and keep local development workable.
- Verification: add a test that asserts the header matches the configured origin and does not fall back to `*`.

#### 2. Audit-log denied admin attempts

- Why: successful admin actions are logged, but denied attempts are still invisible.
- Scope: `admin_commands.py`, `mini_app_api.py`, and focused tests.
- Goal: record an explicit denial event when admin access is rejected, without changing successful-action logging.
- Verification: confirm both a rejected Telegram admin command and a rejected Mini App export create the denial record.

#### 3. Add `POST /queue/resume` to the Mini App API

- **Done.** `POST /queue/resume` was added, and `GET /session/current` now reports `isPaused`. `Commands.tsx` uses both to make Pause/Resume a real toggle.

### Not delegated yet

These need a product decision first, so they should stay out of the ready-to-delegate list until the rule is chosen deliberately.

- **Paid write path:** decide whether it should exist in both Telegram and the Mini App, or remain disabled until the workflow is defined.
- **Fully blacklisted customers:** decide whether queue eligibility should treat them as uncallable or leave the current behavior unchanged.
- **Session timing:** decide whether to keep wall-clock timing or move to an idle-aware model.

## What is currently open

- CORS is still wide open and should be restricted to the real Mini App origin.
- Denied admin attempts are not yet audit-logged.
- The Mini App still has no import flow of its own; importing remains Telegram-only.
- Frontend test coverage is still sparse or absent -- there is no frontend test runner configured yet (no vitest/jest). All frontend changes are validated by typecheck + lint + build + manual diff review, not automated frontend tests. Setting up a frontend test framework is its own decision, flagged as the top open item in `FreikerDialBot_UI_UX_Development_Log.md`.
- Settings > Phone Handling (primary-number preference, quick switching), Display, Queue (pre-ready count, active-queue/new-contacts ordering), most of Search, Language (Russian/Tajik), Accent Color, Animation Intensity, and Version Info are still unimplemented placeholders in `Settings.tsx` (honestly disabled, not faked) -- see the Settings section list there for the full current set.
- Landing's "full-screen" height (`calc(100dvh - 8.5rem)`) is an approximation of the app bar + bottom nav height, not measured against the actual rendered DOM on a real device.

## Recently completed

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
