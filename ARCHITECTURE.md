# Architecture Consolidation Pass

This was an architecture pass, not a feature pass — no UI changes, no new
import capabilities, no new statistics. Everything below either removes
duplication that had crept in across three separate passes of feature
work, or gives two frontends (Telegram bot, Mini App) one shared place
to enforce a rule they'd otherwise each need their own copy of.

---

## 1. Architecture Review (Phase 1)

### What already matched the target architecture

The codebase was in better shape than a from-scratch review might
suggest — three responsibilities were **already** correctly owned and
needed no change at all:

- **Queue, current customer, status transitions** — mostly owned by
  `QueueEngine`. `start_call`'s explicit-customer-id path still writes
  `queue_session` directly via `database.update_queue_session()` rather
  than through a `QueueEngine` method — this was previously documented
  as "closed via `set_active_customer`," but that method does not exist
  in `queue_engine.py`. Corrected here; see `AGENTS.md`'s "Known
  documentation drift." Not fixed as code, since the direct-write path
  works correctly and is covered by tests — adding a wrapper method
  solely to match the old doc claim would be a cosmetic change with no
  behavioral justification.
- **Import** — `importer.py` (orchestration) / `ai_parser.py` (AI-only)
  / `validation.py` (pure, deterministic) were already cleanly split,
  and AI is already correctly isolated to the import step only — no
  other module touches `AIParser`. Goal #6 ("Keep AI isolated to
  importing only") was already true; nothing needed to change here.
- **`bot.py`** was already thin — handler registration only, no
  business logic in the file itself. It matched the Phase 4 target
  ("bot.py should primarily register handlers... call backend
  services") before this pass started.

### What was duplicated (the real findings)

1. **Backend wiring itself was duplicated.** `bot.py` and
   `mini_app_api.py` each independently constructed the exact same
   `Database -> StatisticsEngine -> SessionManager -> QueueEngine`
   sequence. This is precisely the "Business Logic Engine" the target
   diagram calls for as a single node both frontends call — it just
   didn't exist as an actual module yet.

2. **Duration formatting was copy-pasted four times**, in slightly
   different styles but byte-for-byte identical behavior, across
   `statistics_engine.py`, `session_manager.py`, `admin_commands.py`,
   and `mini_app_api.py` (two distinct formatters — a "fine" one and a
   "coarse" one — each duplicated independently). Verified identical
   before touching anything (see the diffs in "Files changed" below).

3. **Authorization existed in exactly one place** (`admin_commands.py`'s
   `is_authorized`, Telegram-only) **while the equivalent Mini App
   endpoint had no check at all.** This is the same class of problem as
   #1 and #2 — a rule that should exist once, applied inconsistently
   because each frontend had grown its own copy (or, in this case, no
   copy at all).

### What was NOT touched, deliberately

- `queue_ui.py` / `telegram_ui.py` rendering logic — genuinely
  presentation-only, not duplicated anywhere (Mini App's JSON shaping in
  `mini_app_api.py` is a different medium serving the same domain data,
  not a copy of the same logic).
- `Database`'s SQL — `StatisticsEngine` runs its own SQL against
  `daily_statistics`/`customer_events` rather than going through
  `Database` methods for everything. This blurs the "Database vs
  Statistics" line slightly, but it's a defensible pattern (each engine
  owns its own tables' queries) and forcing it through `Database`
  wrapper methods would be moving code without improving anything —
  explicitly what this pass was told to avoid.
- Any DB schema changes for future customer-model fields — see the
  Customer Model Review below; this was explicitly review-only.

---

## 2. Dependency Graph

```
FRONTENDS (presentation + request handling only)
┌─────────────────────────────┐     ┌──────────────────────┐
│ bot.py                      │     │ mini_app_api.py       │
│  ├─ telegram_ui.py          │     │  (MiniAppService,      │
│  ├─ queue_ui.py             │     │   MiniAppRequestHandler)│
│  ├─ stats_ui.py             │     └──────────┬─────────────┘
│  └─ admin_commands.py       │                │
└──────────────┬───────────────┘                │
               │                                 │
               └────────────────┬────────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │   backend.py (NEW)       │
                    │  "Business Logic Engine"  │
                    │  build_backend() -> Backend│
                    └────────────┬──────────────┘
                                 │  wires, once
        ┌────────────┬──────────┼───────────┬─────────────┐
        ▼            ▼          ▼           ▼             ▼
  QueueEngine  SessionManager StatisticsEngine  Importer  AIParser
        │            │           │                │           │
        └─────┬──────┴─────┬─────┘                ▼           ▼
              ▼            ▼                  validation.py (pure)
           Database ◄──────┘
              │
              ▼
           SQLite

CROSS-CUTTING (imported directly by both frontends, not through Backend
-- these are policy/utility, not domain state, so they don't belong on
the Backend dataclass):

  security.py    ← admin_commands.py, mini_app_api.py
  formatting.py  ← statistics_engine.py, session_manager.py,
                   admin_commands.py, mini_app_api.py
  telegram_auth.py ← mini_app_api.py only (Telegram-protocol-specific;
                   nothing to share with Telegram's own bot library auth)
  export_engine.py ← admin_commands.py, mini_app_api.py
  logger.py      ← nearly everything
```

**Why `security.py`/`formatting.py`/`export_engine.py` aren't fields on
`Backend`:** `Backend` holds *stateful domain objects* wired together
once per process (a `Database` connection factory, engines that share
that database). `security.is_admin()` and `formatting.format_duration_*`
are pure functions with no state — importing them directly is simpler
and creates no coupling `Backend` would need to manage. Putting stateless
utilities on a stateful container would be exactly the kind of
unnecessary indirection this pass was told to avoid.

---

## 3. Files Changed

### New files

| File | Purpose |
|---|---|
| `backend.py` | `Backend` dataclass + `build_backend()`. The single place `Database`/`StatisticsEngine`/`SessionManager`/`QueueEngine`/`Importer`/`AIParser` get wired together. |
| `security.py` | `is_admin(telegram_user_id, settings)`. The single shared authorization rule. |
| `formatting.py` | `format_duration_fine`/`format_duration_coarse`. The two duration formatters that had been quadruplicated. |
| `test_backend.py` | Confirms `build_backend()`'s wired instances actually share state (same `Database`, same `StatisticsEngine`, etc.) — the property that makes the deduplication safe. |
| `test_security.py` | Unit tests for `is_admin`. |
| `test_formatting.py` | Boundary-case tests for both formatters (0s, 59s, 60s, minutes+seconds, etc). |
| `ARCHITECTURE.md` | This document. |

### Edited files

| File | What changed | Why |
|---|---|---|
| `bot.py` | Uses `build_backend()` instead of manually constructing the service chain; removed now-unused direct imports (`AIParser`, `Database`, `Importer`, `QueueEngine`, `SessionManager`, `StatisticsEngine`, `load_settings`). Every existing `bot_data[...]` key is preserved (pointing at the same instances), so no handler code changed behavior. | Removes duplicate wiring (finding #1). |
| `mini_app_api.py` | `MiniAppService.__init__` uses `build_backend()`; removed the duplicated `_format_duration` method (uses `formatting.format_duration_fine`); **`GET /export` now requires `security.is_admin`** (403 if not); successful exports now write an `admin_action` audit event, matching what Telegram's `/export` gets via `admin_commands.py`. | Removes duplicate wiring (#1), duplicate formatting (#2), closes the authorization gap (#3). |
| `admin_commands.py` | `is_authorized()` now delegates to `security.is_admin()`; removed the two duplicated duration formatters (uses `formatting.py`); `reset()`/`clear()`/`export()` now write an `admin_action` audit event on success via a new `_record_admin_action()` helper. | Same shared rule as Mini App (#3), removes duplicate formatting (#2), adds the audit trail the security review asked about. |
| `session_manager.py` | Removed `_duration_text`/`_fine_duration_text` methods, uses `formatting.py`. | Removes duplicate formatting (#2). |
| `statistics_engine.py` | Removed the module-level `_format_duration` function, uses `formatting.py`; added `"admin_action"` to `EVENT_TYPES`. | Removes duplicate formatting (#2); required by the new audit logging. |
| `test_admin_commands.py` | `_fake_context()` fixture now includes `statistics_engine` (matching what real `bot_data` always has — this was a fixture gap, not a behavior change); `test_clear_command_removes_customers_but_keeps_history` updated to expect and verify the new `admin_action` audit event instead of asserting no new events. | Required by the audit-logging change; the fixture now accurately reflects production `bot_data`. |
| `test_mini_app_api.py` | `authenticated_api_server` fixture now builds an explicit `Settings` (including a known `admin_user_ids`) instead of depending on real environment values; replaced the single anonymous-export test with three: anonymous rejected (403), non-admin rejected (403), admin succeeds with a verified audit trail. | Directly tests the new, deliberate `/export` authorization requirement (#3) — this is a real, intentional behavior change and it's tested as one, not silently patched around. |

### Not changed

Everything else — `queue_engine.py`, `database.py`, `validation.py`,
`ai_parser.py`, `importer.py`, `export_engine.py`, `telegram_auth.py`,
`queue_ui.py`, `telegram_ui.py`, `stats_ui.py`, `config.py`, `logger.py`,
and all frontend (React) files — is untouched. None of them contained
duplication or misplaced business rules that this pass's goals called
for fixing.

---

## 4. Customer Model Review

Current model (`validation.STANDARD_KEYS` / `database.SCHEMA`):
`loan_number`, `first_name`, `last_name`, `phone_numbers` (JSON list),
`balance`, `days_overdue`, plus `status`, `status_timestamp`,
`warning_note` (added via `_migrate` in an earlier pass).

**Good news, no changes needed:** the architecture already supports most
of the requested future fields cleanly, via patterns already proven
twice in this codebase:

- **Monthly Payment, Current Overdue Payment, Remaining Loan Balance,
  Original Loan Amount** — each should follow the *exact* pattern
  `balance`/`days_overdue` already use: a nullable `TEXT` column (not
  numeric — `balance`/`days_overdue` are deliberately `TEXT` so OCR can
  store partial/masked/illegible values, e.g. `""` for "not visible";
  new financial fields should match that convention for consistency),
  added via `Database._migrate` (the same additive-migration mechanism
  that added `warning_note`), a `STANDARD_KEYS` entry, and a
  `normalize_customer()` case. If they should be OCR-extracted, the
  `AI_PROMPT`/`SYSTEM_PROMPT` schema in `ai_parser.py` needs the new
  keys too. This is a well-worn path, not new architecture.

- **Call History / Notes (plural)** — **this already exists at the data
  layer and doesn't need new schema.** `customer_events` (with
  `customer_id`, `loan_number`, `event_type`, `event_timestamp`,
  `telegram_user_id`, `notes`) already captures every status change and
  every `customer_note_added` event, per customer, with who and when.
  What's missing is purely a *query + presentation* gap: no
  `Database.get_customer_events(customer_id)` method exists yet, and
  neither frontend's customer payload pulls from it (Mini App's
  `_customer_payload` only surfaces the single `warning_note` column).
  This is genuinely just "expose what's already there" work, not a
  schema change — flagged as a recommendation, not implemented here
  (adding an unused method would be new functionality this pass wasn't
  scoped for).

- **Primary Phone** — currently implicit (`phone_numbers[0]`, decided
  independently by each frontend — Mini App picks index 0, Telegram's
  `queue_ui.render_customer` shows all of them). If "primary" becomes
  an explicit feature, it should be a deliberate convention (e.g. always
  keep the primary at index 0, enforced on edit) rather than adding a
  parallel field, to avoid the two ever disagreeing.

- **Tags** — same pattern as `phone_numbers`: a JSON-list `TEXT` column,
  when needed.

**Needs a real design decision (not just "add a column"):**

- **Blacklist Status** — the brief lists "Blacklist by customer" and
  "Blacklist by phone number" as two *separate* future features, and
  that distinction matters architecturally: a `customers` row can be
  (and is) deleted (`Database.delete_customer`), but a phone-level
  blacklist needs to survive that and survive across different loans
  reusing the same number. Recommendation: two decoupled mechanisms —
  a nullable `is_blacklisted` column on `customers` (customer-level,
  same migration pattern as above) **and** a separate
  `blacklisted_phones` table keyed on the phone number itself, with its
  own lifecycle independent of any customer row. Don't try to make one
  mechanism serve both.

**Confirms two of the stated goals are already true, no work needed:**
Goal #2 ("operator should never need the original spreadsheet/screenshot
after import") — already true; `importer.py` saves originals to
`ORIGINALS_DIR` and everything downstream reads from the database, never
the source file. Goal #1 ("operator should never need to remember
anything") — already substantially true via `warning_note`'s automatic
same-day-recontact detection and the `customer_events` history; the
"Notes" query gap above is the main remaining piece.

---

## 5. Security Review

| Area | Status | Recommendation |
|---|---|---|
| **Mini App authentication** | Telegram `initData` HMAC validation implemented (`telegram_auth.py`, prior pass), wired into every Mini App request. **Fixed in the 2026-08-05 priority security pass:** auth is now mandatory by default — missing/malformed credentials get a 401 on every real endpoint (`_API_PATHS`); `/` and static assets stay open, as they must. `MINI_APP_ALLOW_ANONYMOUS=1` is an explicit, off-by-default dev-only escape hatch. | None further needed for the cutover itself. See `MINI_APP_API.md`. |
| **Export authorization** | **Fixed this pass.** `GET /export` now requires `security.is_admin`, matching Telegram's `/export` exactly, using the same shared rule. | None further needed for parity; if finer-grained permissions are wanted later (e.g. "can export" separate from "can reset"), that's a `security.py` extension — see Tech Debt. |
| **Permissions** | Single binary level: admin or not, via `ADMIN_TELEGRAM_USER_IDS`. No RBAC. | Adequate for current feature set (reset/clear/export are the only gated actions on either frontend). Don't build RBAC speculatively — revisit only when a second permission tier is actually needed (e.g. "can edit customers" separate from "can export"). |
| **Audit logging** | **Improved this pass.** Successful `reset`/`clear`/`export` actions (both frontends) now write an `admin_action` event to `customer_events`, attributed to the acting `telegram_user_id`, reusing the existing event-history mechanism rather than a new table. | Denied/unauthorized attempts are **not** currently logged (only successes) — worth adding if detecting probing/abuse attempts matters; deliberately not done here since it changes log volume and semantics in a way worth deciding separately. |
| **Anonymous API access** | **Fixed in the 2026-08-05 pass** — see Authentication row above. CORS is still `Access-Control-Allow-Origin: *` on every response. | CORS restriction to the real Mini App origin is the one piece of this row still open — see `BACKLOG.md` #2. |

---

## 6. Remaining Technical Debt

Carried forward from `BACKLOG.md` (not re-litigated here) plus what
this pass surfaced:

1. ~~Anonymous Mini App access is still the default outside `/export`~~ —
   fixed 2026-08-05, see Security Review above.
2. CORS wide open (`*`) — still open, same section.
3. No `POST /queue/resume`, no Mini-App-side import, no Telegram-side
   notifications, no "Paid" button in Telegram's `queue_ui.py` (Mini
   App has it, Telegram doesn't — a feature-parity gap, not a bug).
4. `daily_statistics` doesn't track `invalid_number` or `paid` as their
   own buckets — `/statistics`'s `wrongNumber`/`bestDay` fields are
   still placeholders. Out of scope here (would be *adding* statistics,
   explicitly disallowed this pass).
5. Denied admin attempts aren't audit-logged, only successes (see
   Security Review).
6. `StatisticsEngine` runs its own SQL against shared tables rather than
   going through `Database` methods for everything — noted as a design
   observation in the Architecture Review, not a defect; revisit only
   if it starts causing real confusion, not preemptively.
7. Customer call-history/notes are captured in `customer_events` but not
   yet queryable or exposed to either frontend (see Customer Model
   Review) — the clearest "cheap win" for a future pass.
8. `test_import_pipeline.py`'s one pre-existing, unrelated failure
   (confirmed against the original codebase in an earlier pass) is
   still present and still untouched.

---

## 7. Recommendations for the Next Pass

In rough priority order:

1. **Expose customer call history.** Add
   `Database.get_customer_events(customer_id)` and surface it in both
   `queue_ui.render_customer` (Telegram) and `_customer_payload` (Mini
   App). Directly serves goal #1 ("operator should never need to
   remember anything") and the data already exists — this is the
   highest value-to-effort item on the list.
2. ~~Decide the anonymous-access cutover.~~ Done 2026-08-05 — auth is
   mandatory by default now. CORS is the one piece of this that's still
   open (tighten once the real Mini App origin is stable).
3. **Blacklist-by-phone**, as its own table (see Customer Model Review)
   — independent of customer-row lifecycle, needed before
   blacklist-by-customer would even be safe to rely on for repeat
   offenders across re-imports.
4. If/when a second Mini App admin-style endpoint is added (e.g.
   `/queue/reset`), gate it with `security.is_admin` from day one —
   the whole point of this pass was making that a one-line addition
   instead of a new gap.

---

# Addendum: Customer History, Search, Edit, and Blacklist

Follow-up pass implementing recommendation #1 above (expose customer
call history) plus search, editing, and blacklist — the other named
future features from the original architecture review's Customer Model
Review section.

## What this pass built

**One shared record source, `Database.get_customer_record()`** —
combines the customer row, per-phone and per-customer blacklist state,
notes (filtered from `customer_events`), and full event history, in one
method. Both Telegram (`customer_ui.render_customer_record`) and the
Mini App (`GET /customer/record`) call this exact method — neither
assembles its own version.

**Repository layer (`database.py`):** `search_customers` (substring
match across loan number / name / phone, any status — not just
currently-queued), `get_customer_events`, `update_customer_fields`
(explicitly excludes `loan_number` and `status` — editing those is a
different operation, not a field correction), `set_customer_blacklisted`,
plus a new `blacklisted_phones` table with its own CRUD, independent of
the `customers` table lifecycle (see the original Customer Model Review
for why phone-level blacklist has to survive customer-row deletion).

**Orchestration layer (`queue_engine.py`):** `edit_customer`,
`blacklist_customer`, `blacklist_phone`, `unblacklist_phone` — each
pairs a `Database` write with an audit event (`customer_edited`,
`customer_blacklisted`/`unblacklisted`, `phone_blacklisted`/
`unblacklisted`), following the exact pattern `apply_action`/
`delete_customer` already established. `edit_customer` records exactly
what changed (`"balance: '500' -> '750'"`), and is a genuine no-op (no
audit event, no write) when nothing actually changed.

**Telegram (`customer_ui.py`, new module):** `/customer <query>` (search
→ single record or tappable list), a "ℹ️ More Info" button added to the
existing call card (`queue_ui.queue_keyboard`) routing to the same view,
`/edit`, `/blacklist` / `/unblacklist`, `/blacklist_phone` /
`/unblacklist_phone`. Kept as its own module rather than folded into
`queue_ui.py` specifically so the active-call card stays lightweight
(Phase 5's requirement) while detailed history lives in its own,
separately-testable place.

**Mini App (`mini_app_api.py`):** `GET /customer/search`,
`GET /customer/record`, `POST /customer/edit`, `POST /customer/blacklist`,
`POST /phone/blacklist` — backend/HTTP only, per this pass's explicit
scope ("do not focus on UI styling"). No new React screens were built;
the endpoints exist so a future frontend pass has zero backend work left
to do, same pattern as the Mini App launch-prep pass.

## Deliberate decisions worth knowing about

- **Blacklisting does not affect queue selection.** A blacklisted
  customer still appears in the normal calling queue; blacklist is
  state + audit trail only in this pass. Tested explicitly
  (`test_blacklisting_does_not_affect_queue_selection`) so this is a
  known, verified behavior, not an oversight. See Backlog.
- **Edit/blacklist actions are not admin-gated**, matching the existing
  precedent that single-record actions (warned, skip, call_later) are
  open to any operator, while only whole-dataset actions (reset, clear,
  export) require admin authorization via `security.is_admin`. This was
  a real design choice, not a default — flagged explicitly rather than
  silently picked.
- **`/edit` requires an exact loan number or internal id**, not a fuzzy
  search match — unlike `/customer` (read-only, fuzzy is fine),
  mutating commands need precision to avoid editing the wrong person
  from an ambiguous partial match.
- **No new financial fields added** (monthly payment, a separate
  "overdue amount" in currency) — per the original Customer Model
  Review, `balance`/`days_overdue` are the only such fields that
  actually exist; inventing new columns wasn't asked for and would
  contradict "if a field already exists, expose it instead of inventing
  a new storage path."

## Remaining gaps for the next pass

1. **No Mini App frontend UI** for any of this (search screen, customer
   detail screen, edit form, blacklist toggle) — backend-only, as scoped.
2. **Blacklisted customers aren't skipped in the queue.** If that's
   wanted, it's a `QueueEngine._find_next_actionable` change — should be
   a deliberate follow-up decision, not bundled in silently here.
3. **`update_customer_fields` doesn't validate `balance`/`days_overdue`
   as numeric-looking** — consistent with import-time validation (which
   also just stores whatever OCR/text produced), but worth a decision if
   stricter validation is wanted for manual edits specifically.
4. **Search has no pagination** — capped at a flat limit (20 for Mini
   App, 10 for Telegram's inline results). Fine at current data volumes;
   revisit if customer counts grow enough for that cap to matter.
5. **`/edit`'s `phone_numbers=` syntax is comma-separated plain text** —
   works, but is the roughest part of the UX; a proper Mini App edit
   form would handle this far more cleanly once built.

---

# Addendum: Customer Data Quality Pass

Follow-up pass focused entirely on the customer data model and import
quality, per the brief: "the operator should never need the original
spreadsheet or CRM again." No Mini App, deployment, or UI-styling work
was done in this pass.

## Phase 1 finding: a real gap between modules, fixed first

Before any new work, a review of the import pipeline surfaced that
`database.py` was missing methods every other live module already
depended on: `search_customers`, `get_customer_events`,
`update_customer_fields`, `set_customer_blacklisted`,
`is_phone_blacklisted`, `blacklist_phone`/`unblacklist_phone`, and
`get_customer_record` (plus their `async_*` wrappers). `customer_ui.py`,
`test_customer_ui.py`, and `test_database.py` all called these; without
them the customer-history/search/edit/blacklist surface documented
above as "Resolved" was actually non-functional, and 40 tests failed on
a fresh run. Likewise `queue_engine.py` was missing `edit_customer`,
`blacklist_customer`, `blacklist_phone`, and `unblacklist_phone`, and
`statistics_engine.py`'s `EVENT_TYPES` didn't yet include
`customer_edited`/`customer_blacklisted`/`customer_unblacklisted`/
`phone_blacklisted`/`phone_unblacklisted`/`customer_note_added`. All of
this has been restored -- it's implementation that already existed
elsewhere in the project's history and simply hadn't made it into these
three files. `bot.py` also didn't register `/customer`, `/edit`,
`/blacklist`, `/unblacklist`, `/blacklist_phone`, `/unblacklist_phone`,
or the "More Info" callback at all -- these are now wired in, and
`queue_ui.queue_keyboard` now includes the "ℹ️ More Info" button on both
the normal and `needs_review` card layouts, so Phase 5's "Main Card /
More Info / History" review has actual screens to review.

## Phase 2: customer model extended

Added three new nullable `TEXT` columns, following the exact convention
`balance`/`days_overdue` already established (never numeric, since OCR
data is frequently partial or illegible; `""` means "not visible"):

- `monthly_payment` -- the recurring installment amount.
- `current_overdue_amount` -- the dollar amount currently past due.
  Deliberately distinct from `days_overdue`, which is a day count, not
  a currency figure -- these were being conflated in the original brief
  and needed separating.
- `original_loan_amount` -- the original principal.

Also added `last_edited_timestamp`, set automatically by
`Database.update_customer_fields` whenever any field is corrected.
This is intentionally separate from `status_timestamp` (which tracks
call outcomes) -- an operator can now tell "when was this customer last
called" apart from "when was this record last corrected," which the
model couldn't previously express. Both are exercised by
`test_database.py::TestLastEditedTimestamp`, including a regression
test that editing a field doesn't disturb the call-outcome timestamp.

**Primary Phone** stays implicit (`phone_numbers[0]`), per the original
recommendation -- but `Database._customer_from_row` now surfaces it
explicitly as a `primary_phone` key on every returned customer dict
(computed, not stored), so every caller uses the same definition instead
of each frontend picking index 0 independently. `customer_ui`'s More
Info view now visibly marks the primary number.

**Notes, Call History, Blacklist State** -- these were already modeled
via `customer_events` and the `blacklisted_phones` table; this pass's
contribution was restoring the `database.py` methods that actually read
and write them (see Phase 1 finding above), not adding new schema.

## Phase 3 & 4: import quality and formatting

- `ai_parser.AI_PROMPT`/`SYSTEM_PROMPT` extended from 6 to 9 fields,
  with an explicit rule (#9 in `AI_PROMPT`, and a dedicated line in
  `SYSTEM_PROMPT`) telling the model never to conflate `balance`,
  `monthly_payment`, `current_overdue_amount`, and
  `original_loan_amount` -- if only one dollar figure is visible, it
  goes in `balance` and the others stay `""`. This was the main import
  risk with adding more currency-shaped fields: an AI model asked for
  four dollar amounts when a screenshot shows one will often guess or
  duplicate it across fields unless explicitly told not to.
- `validation.normalize_money()` (new): strips `"$"` and thousands
  commas from any of the four currency fields, deterministically, after
  AI/JSON/Excel extraction -- consistent with Phase 3's instruction to
  prefer deterministic validation over a more complex AI prompt.
  `validation.normalize_loan_number()` (new): a named pass-through
  function (loan numbers are opaque identifiers and were already just
  trimmed) so the "what happens to a loan number on the way in" question
  has one answer, not an inlined `.strip()`.
- `ai_parser._map_common_keys` and `validation._XLSX_COLUMN_ALIASES` both
  extended with aliases for the three new fields (e.g. "Monthly
  Payment", "Overdue Amount", "Original Loan Amount", "Principal"), so
  human-readable headers/keys map the same way `balance`/`days_overdue`
  already did.
- `formatting.py` gained four new **display-only** helpers --
  `format_currency` (`"784234385.32"` -> `"784,234,385.32"`),
  `format_phone_display` (`"15551234567"` -> `"+1 (555) 123-4567"`),
  `format_loan_number` (pass-through, for a single point of control),
  `format_date` (ISO timestamp -> `"Jul 18, 2026"`). None of these touch
  what's stored -- `normalize_money`/`normalize_loan_number` (validation
  time) and `format_currency`/`format_phone_display`/`format_date`
  (display time) are deliberately separate concerns, so a future display
  format change never requires a data migration.

## Phase 5: card review

- **Main card** (`queue_ui.render_customer`): now shows Monthly Payment
  and Amount Overdue (formatted via `format_currency`) *only when
  present*, in addition to the existing Balance/Days Overdue/Phone --
  these are the two new fields an operator is most likely to be asked
  about mid-call. Original Loan Amount was deliberately left off the
  main card (per "don't overwhelm the default screen") since it's
  rarely relevant to an active collections conversation.
- **More Info** (`customer_ui.render_customer_record`): now shows all
  four currency fields, the primary-phone marker, and both
  `import_timestamp` and `last_edited_timestamp` (via `format_date`) --
  this is the "full loan detail" screen, so nothing is held back here.
- **History**: unchanged -- already sourced from `customer_events` via
  `Database.get_customer_events`, which now actually works (Phase 1).

## Phase 6: testing

- `test_formatting.py` (new): boundary tests for all four new display
  helpers plus the pre-existing duration formatters.
- `test_database.py`: new `TestExtendedFinancialFields` (new columns
  default to `""`, persist through insert, `primary_phone` is computed
  correctly) and `TestLastEditedTimestamp` (unset initially, set on
  edit, distinct from `status_timestamp`).
- `test_import_pipeline.py`: new `TestExtendedFinancialFieldImport` --
  JSON import with `$`/comma-formatted values, missing-fields-are-fine,
  human-readable AI key mapping, Excel alias headers, `normalize_money`
  unit tests, and an export-includes-new-columns regression test.
- `test_queue_engine.py`: updated the two keyboard-shape assertions for
  the restored "More Info" row, and added a dedicated test for the
  button itself.
- Full suite: 192 passed, 1 pre-existing failure (documented in
  `BACKLOG.md`, unrelated to this pass, left untouched).

## What was deliberately NOT done

- Mini App (`mini_app_api.py`) was given the same three new fields on
  its customer payload for basic data parity, but no new endpoints, no
  auth/security wiring, no launch/deployment work -- explicitly out of
  scope for this pass.
- No AI prompt changes beyond the schema/field-conflation rule above --
  Phase 3 explicitly asked not to overcomplicate the prompt.
- No UI redesign -- the main card's structure, button layout (aside
  from the restored More Info row), and Telegram message formatting are
  unchanged.

