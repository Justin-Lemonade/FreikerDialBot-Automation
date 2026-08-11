# FreikerDialBot UI/UX Development Log

This is the authoritative backlog and history for the Mini App frontend.
Prior implementation summaries -- including Claude's own, in chat -- may
be incomplete, partially correct, or outdated. **The repository is the
source of truth.** Before starting a new pass, verify claims below
against the actual code rather than trusting the prose.

This file did not exist before UI Pass 4 (the entries below for Passes
1-3 are reconstructed from `PROJECT_STATUS.md` and commit history, not
from a log kept at the time -- treat their detail level accordingly).
From Pass 4 onward, update this file at the end of every pass.

---

## UI Pass 4 (this pass)

**Brief:** deliver a noticeably better product against an explicit
priority list, not just check off individual requirements. Included an
instruction to independently re-audit the app for dead buttons/broken
controls beyond what was explicitly listed.

### Self-review

**Claimed complete (by priority number in the brief):**
1. Home screen -- Landing.tsx created, split from the calling workflow
2. Call button -- already fixed in Pass 3, re-verified working here
3. Customer workflow -- More Info moved below outcome buttons, dead
   Call Again/Note buttons replaced
4. Customer card -- audited; indexLabel dead-prop wired to real data
5. Commands -- Pause/Resume/Export wired to real backend routes, real
   typed command parser added
6. Bottom nav -- font/touch-target/selected-state polish
7. Settings -- touch-target fixes (32px -> 44px)
8. Independent review -- found and fixed a second dead button
   (SessionComplete's Export) beyond what was explicitly flagged

**Actually complete, verified (typecheck + lint + build + relevant
backend tests passing, commit confirmed on GitHub):** all of the above.
Every commit in this pass was individually verified against the GitHub
API after pushing, not just trusted from the `git push` exit code.

**Missed / not done this pass:**
- Priority 2 (dedicated responsive-layout audit) was not done as its
  own standalone pass -- responsive/touch-target issues were fixed
  opportunistically while working on other priorities (nav, Settings,
  card), not systematically screen-by-screen.
- Landing's "full-screen" height (`calc(100dvh - 8.5rem)`) is an
  approximation of the app bar + bottom nav height, not measured
  against the actual rendered DOM. Likely close but unverified on a
  real device.
- Settings > everything outside Calling Behavior / Appearance /
  Admin-Diagnostics-partial is still an honest disabled placeholder
  (Phone Handling, Display, Queue, Search, Language, most of
  Admin/Diagnostics). Not a regression -- deliberately not faked -- but
  worth stating plainly rather than letting "Settings grouped and
  useful" read as "Settings complete."

**Regressions introduced and caught within this pass:** the phone
numbers + More Info work in Pass 3 made `CustomerCard` taller, working
against "Home must not require constant scrolling" -- caught and fixed
by compacting the phone/More-Info row (commit `1174d74`) before this
pass's Home-screen restructuring made the card the *only* thing on the
`calling` screen (previously it shared space with more UI).

**Design problems found beyond the explicit checklist:**
- `mini_app_api._map_outcome()` had no entries for `"call_again"` or
  `"note"` -- both outcome-button values `OutcomeButtons.tsx` used to
  send. Every tap of either button returned a real backend error. This
  had shipped in Pass 3 without being caught.
- `SessionComplete`'s Export button had no `onClick` handler at all.
- `CustomerCard`'s `indexLabel` prop was declared but never passed by
  any caller.
- `Commands.tsx` left `Pause Queue`/`Export Data` permanently disabled
  even though the backend fully supported both (`queue_engine.pause`
  existed; `resume` existed but had no route until this pass added
  `POST /queue/resume`).

**Highest-priority items for the next pass, in order:**
1. A real, screen-by-screen responsive-layout audit (Priority 2 as its
   own pass, on actual narrow/short viewports, not opportunistic fixes).
2. Decide and implement Settings > Phone Handling (primary-number
   preference, quick switching) -- currently the most fleshed-out
   "empty" category and the most naturally next-in-line given phone
   numbers are now fully exposed elsewhere.
3. Pre-ready N-deep customers (Settings > Queue) -- the single largest
   remaining gap between the Settings categories and real backend
   capability.

### Commits this pass
- `1174d74` Compact CustomerCard phone/More Info row
- `bafacbf` `POST /queue/resume` + `isPaused` on session payload
- `9e8a694` Real Home/Landing screen; fixed dead Call Again/Note buttons
- `54266e1` Real typed commands, Pause/Resume, Export
- `e758d39` Bottom nav polish
- `a6797f2` Wired dead `indexLabel` prop
- `0db81d1` Settings touch-target fixes
- `9a5785b` Fixed SessionComplete's dead Export button

---

## UI Pass 5 (this pass)

**Brief:** the three highest-priority items UI Pass 4 left for next
time, in order: (1) a real screen-by-screen responsive-layout audit,
(2) Settings > Phone Handling, (3) Pre-ready N-deep customers
(Settings > Queue).

### Self-review

**Claimed complete:**
1. Responsive audit -- found and fixed a real bug: Landing's
   `min-h-[calc(100dvh-8.5rem)]` (flagged as unverified in Pass 4) was
   double-counting the bottom-nav clearance that `MainLayout`'s
   `<main>` already reserves via `pb-28`, forcing an unnecessary
   scrollbar on Home. Fixed by making `<main>` a flex column and
   Landing `flex-1`/`min-h-0`, so it fills exactly the space its
   parent has left -- no guessed constant at all, not just a better
   guess. Rest of the audit (Home/Calling, CustomerCard, OutcomeButtons,
   Search, Commands, CustomerDetail, SettingsDrawer, SessionComplete)
   found no other viewport-height magic numbers and no fixed pixel
   widths that would clip at 320px.
2. Settings > Phone Handling -- Primary Phone Preference (real
   GET/POST /settings setting, backend-enforced reordering in
   `_ordered_phone_numbers`/`_customer_payload`, blacklist fallback
   verified) and Quick Number Switching (tap a number on the call card
   to make it the one CALL CUSTOMER dials, on top of the existing
   tap-to-dial behavior which is unchanged).
3. Settings > Queue > Pre-ready Count -- real 0-3 setting;
   `GET /queue/upcoming?count=N` (additive, backward-compatible with
   the existing single-customer callers) previews that many upcoming
   customers using the same `get_next_actionable_customer`
   ordering/blacklist-skipping the single-customer form already used;
   frontend prefetches and renders them as a non-interactive "UP NEXT"
   strip on the calling screen so the setting has an observable effect.

**Actually complete, verified:** all of the above --
`pytest tests/ -q` (400 passed, up from 391), `npx tsc -b --noEmit`
clean, `npm run test` (38 passed, up from 37), `npm run build` clean,
`npx oxlint` (0 warnings/errors). Commits pushed and verified against
the GitHub API (HEAD SHA + per-file diff) after each push, not just
trusted from `git push`'s exit code.

**Explicitly not done / left as placeholders:** Display, Search,
Language, and the remaining Queue rows (Active Queue vs New Contacts,
Resume/Restart Behavior) are still honest disabled placeholders --
out of scope for this pass's three listed priorities, not silently
dropped.

**Design/architecture notes for whoever picks this up next:**
- `first_non_blacklisted_phone` itself was left untouched (still
  first-in-list-order); the preference is applied one layer up, by
  reordering the candidate list `_customer_payload` hands it. Keeps
  the fallback logic (skip blacklisted, fall back to next available)
  in exactly one place.
- `queue_upcoming`'s `count` param is additive/optional specifically
  to avoid a breaking change to the existing single-customer response
  shape and its test coverage -- worth keeping that contract in mind
  if `/queue/upcoming` is touched again.
- The "UP NEXT" strip is deliberately non-interactive (no tap-to-jump)
  to keep Pre-ready Count a preview of the real queue, not a second
  queue-manipulation surface living in the frontend.

### Commits this pass
- `5171963` Fix Landing screen overflow (flex sizing, not a guessed constant)
- `86d716c` Backend: Phone Handling + Pre-ready Count settings
- `fcbcb01` Frontend: wire both settings in

---

## UI Pass 3

**Brief (approximate, reconstructed from `PROJECT_STATUS.md`):** compact
the progress header and scope it to relevant screens, expose both phone
numbers and More Info from the live workflow, fix card-slide animation
clipping, make Search keyboard-safe with match highlighting, group
Settings into real categories, fix the Call button.

**What shipped:**
- Progress header compacted to one row, scoped to calling-related
  screens.
- Both phone numbers exposed (`phones[]` on the customer payload) and
  More Info made reachable from the live card (later relocated in
  Pass 4).
- Card-slide `overflow-x` clipping bug fixed.
- Search made keyboard-safe with match highlighting.
- Settings grouped into categories (later re-grouped again in Pass 4
  once the Home/Landing split changed what "real" meant for a few
  rows).
- Found and fixed the actual Call button bug: `tel:` navigation was
  happening after an `await`, breaking the mobile browser's
  user-gesture requirement.

**What Pass 4 found wrong with Pass 3's own work:** the phone-number
exposure made the card taller, cutting against "no constant scrolling"
-- not caught until Pass 4's audit.

---

## UI Pass 2 (Max Call Attempts / Auto Advance)

Implemented Max Call Attempts (`customers.attempt_count`, generic
`app_settings` table, enforcement in `QueueEngine.restart_call_later`)
and Auto Advance (gates whether the next customer replaces the current
card immediately or waits for an explicit tap) as real, backend-enforced
settings rather than placeholders. `GET/POST /settings` added.

---

## UI Pass 1 (repo stabilization)

Not a UI pass in the strict sense -- added `setup.sh`/`setup.ps1`,
`doctor.py`, fixed fresh-clone failures, backend test suite brought to
330+ passing. Recorded here because it's the baseline every later pass
built on.
