# Backlog — known issues and future-work items

Running list of things noticed but deliberately not fixed, because
they're out of scope for the task at hand, a decision you should make
rather than one made silently, or a pre-existing issue flagged rather
than "fixed" without you seeing it.

For the full writeup behind each item below (why it matters, what the
fix would look like), see `ARCHITECTURE.md`'s Security Review and Tech
Debt sections — this file stays a short pointer list, that one has the
reasoning.

## Resolved

- ~~No Telegram identity verification on Mini App requests~~ — fixed.
  `telegram_auth.py` validates `initData`; `telegram_user_id` flows
  through to `customer_events`.
- ~~`start_call`'s explicit-customer-id path bypassed QueueEngine~~ —
  **correction (this pass): not actually fixed.** This was previously
  marked resolved "via `QueueEngine.set_active_customer()`," but that
  method does not exist in `queue_engine.py` — confirmed by direct grep.
  `start_call` still calls `database.update_queue_session()` directly.
  Left as-is: the direct-write path is correct and tested; adding a
  wrapper method now would only be to match the old (wrong) doc claim,
  not because the architecture needs it. See `AGENTS.md`.
- ~~Mini-App-run sessions never got finalized~~ — fixed; `get_current_session()`
  now finalizes them, with a regression test guarding the "re-polling
  spawns a new session" failure mode that fix could have introduced.
- ~~No Telegram-side Mini App launch mechanism~~ — fixed. Menu button +
  `/app` command.
- ~~**`GET /export` has no authorization gate**~~ — **fixed this pass.**
  Now requires `security.is_admin`, matching Telegram's `/export`
  exactly, via the new shared `security.py`. Tested (anonymous → 403,
  non-admin → 403, admin → 200 + audit trail).
- ~~Backend wiring duplicated between `bot.py` and `mini_app_api.py`~~ —
  fixed via `backend.py`'s `build_backend()`.
- ~~Duration formatting duplicated 4x across `statistics_engine.py`,
  `session_manager.py`, `admin_commands.py`, `mini_app_api.py`~~ —
  fixed via `formatting.py`.
- ~~No audit trail for admin actions (reset/clear/export)~~ — fixed;
  both frontends now write an `admin_action` event on success.
- ~~Customer call history/notes exist in `customer_events` but aren't
  queryable or exposed to either frontend~~ — **fixed.**
  `Database.get_customer_record()` is the one shared source; Telegram's
  `/customer` + "More Info" and the Mini App's `GET /customer/record`
  both use it. See `ARCHITECTURE.md`'s addendum.
- ~~Blacklist (by customer, by phone) not implemented~~ — **fixed.**
  `QueueEngine.blacklist_customer`/`blacklist_phone` with full audit
  trail, exposed via Telegram commands and Mini App endpoints.
- ~~No search~~ — **fixed.** `Database.search_customers`, exposed via
  Telegram's `/customer` and the Mini App's `GET /customer/search`.
- ~~No customer editing~~ — **fixed.** `QueueEngine.edit_customer`,
  exposed via Telegram's `/edit` and the Mini App's `POST /customer/edit`.
- ~~`database.py` was missing search/edit/blacklist/history methods
  that `customer_ui.py`, `queue_engine.py`, and their tests already
  depended on~~ — **fixed.** These had been documented as done in this
  file and in `ARCHITECTURE.md` but were absent from the live
  `database.py`/`queue_engine.py`/`statistics_engine.py`, and `bot.py`
  never registered the commands or the "More Info" callback at all --
  40 tests were failing as a result. Restored in the customer-data-
  quality pass; see `ARCHITECTURE.md`'s addendum.
- ~~Customer model missing Monthly Payment, Current Overdue Amount, and
  Original Loan Amount~~ — **fixed.** Three new nullable `TEXT` columns
  following the `balance`/`days_overdue` convention, extracted by the
  importer/AI parser, editable via `/edit`, and shown on both the main
  call card and the More Info screen. See `ARCHITECTURE.md`'s addendum.
- ~~No way to tell when a customer record was last corrected, as
  opposed to when they were last called~~ — **fixed.** New
  `last_edited_timestamp`, set by `update_customer_fields`, distinct
  from `status_timestamp`.
- ~~Blacklisted customers aren't skipped in the queue~~ — **fixed.**
  `QueueEngine.next_customer()` (the mutating advance path used after
  every real Contacted/Didn't Answer/etc. outcome) now skips blacklisted
  customers, mirroring the read-only `peek_next_customer()`'s existing
  filter. Previously only the read path was safe; the actual operator
  workflow could still land on a blacklisted customer. Two new tests
  (`test_next_customer_never_selects_a_blacklisted_customer`,
  `test_apply_action_never_advances_into_a_blacklisted_customer`) verify
  this through the real `apply_action` path, not just the peek path the
  existing Mini App test already covered.
- ~~Frontend never preloaded the next customer~~ — **fixed.** `App.tsx`
  now calls the existing `GET /queue/upcoming` (already blacklist-safe on
  its own) whenever the current customer changes, best-effort, and
  `Home.tsx`'s "Next up" card — previously mislabeled and actually
  re-displaying the *current* customer — now shows the real preloaded
  one, with the current customer getting its own correctly-labeled card.
- ~~**CI's "Backend tests (Python)" job has failed on every single run
  since CI was introduced (commit `c521a6f`) — 7/7 runs, always at test
  *collection*, never actually executing a test.**~~ — **root-caused and
  fixed.** `pytest tests/ -q` (the exact command CI runs) cannot import
  repo-root modules (`database`, `config`, `backend`, etc.) from files
  under `tests/`, because nothing put the repo root on `sys.path` for
  that invocation style. `python -m pytest tests/ -q` — the command used
  to produce every "N passed" figure in this file and in
  `PROJECT_STATUS.md` — masked this completely, because `python -m`
  always prepends the current working directory to `sys.path` on its
  own; bare `pytest` does not. Confirmed by reproducing CI exactly
  (fresh venv, fresh `pip install`, CI's dummy env vars, bare `pytest`
  binary): 14/14 test modules failed to collect with
  `ModuleNotFoundError`. Fixed with a new `pytest.ini` (`pythonpath = .`),
  which fixes both invocation styles identically rather than relying on
  `python -m`'s side effect. Re-verified after the fix: bare `pytest`
  and `python -m pytest` both now pass 264/264. No CI workflow change
  needed — `ci.yml`'s existing `pytest tests/ -q` line now works as-is.

## Still open

### Security

1. **Auth enforcement is opt-in for most endpoints, not mandatory.**
   Requests with no `Authorization` header are still let through
   anonymously everywhere except `/export`. Intentional until the real
   frontend always sends `initData` — see `MINI_APP_API.md`.
2. **CORS is wide open** (`Access-Control-Allow-Origin: *`). Restrict to
   the real Mini App origin once one exists.
3. **Denied admin attempts aren't audit-logged, only successes.** Worth
   adding if detecting probing/abuse matters — deliberately not bundled
   into this pass since it changes log semantics/volume and is worth
   deciding on its own.

### Correctness / data quality

4. Historical `customer_events` rows from before notes got their own
   `customer_note_added` type may still be mis-tagged as
   `customer_warned` — not fixable retroactively without a data audit.
5. `average_seconds_per_customer` still uses session-duration ÷
   handled-count rather than the real per-call `duration_seconds` now
   being persisted — a deliberate decision point, not changed silently.
6. `/statistics`'s `wrongNumber`/`bestDay` fields are permanent
   placeholders — `StatisticsEngine` doesn't track those buckets. Out of
   scope for "expose what exists" (would mean *adding* statistics).

### Missing endpoints / features

7. No `POST /queue/resume`.
8. No Mini-App-side import flow (screenshots/text/files still Telegram-only).
9. **Correction (this pass): `paid` has no real write path anywhere.**
   Previously framed as "a real `QueueEngine` action" with only a
   frontend-parity gap. Confirmed by direct grep: `paid` exists only as
   a schema-level enum value (`QUEUE_STATUSES`, `status_counts()`).
   `QueueEngine.apply_action`'s `ActionStatus` type does not include it,
   and nothing anywhere ever calls `update_customer_status(..., "paid")`.
   The Mini App's Paid button is now disabled with an honest "not yet
   available" state (see `OutcomeButtons.tsx`) rather than offering an
   action that always fails or inventing a separate write path the
   Telegram bot doesn't share. Implementing real Paid support is a
   product decision requiring a real `apply_action` status + Telegram
   button, not something to add silently to close this gap.
10. No Telegram-side notifications for Mini App activity.
11. **Correction (this pass): `POST /call/return` does not exist.**
    Previously documented as "exists (backend prep)," but confirmed
    absent from `mini_app_api.py`'s route list. Not adding it
    speculatively — no current caller needs it, and inventing an
    unused endpoint just to match the old doc claim isn't justified.
    Add for real if/when the frontend's "operator returned from a call"
    flow actually needs a dedicated event.
12. **No Mini App frontend UI** for search/customer-detail/edit/blacklist
    — those endpoints exist backend-only (this pass was explicitly
    scoped to avoid new UI/styling work). See `ARCHITECTURE.md` addendum.
13. *(Resolved this pass — see "Resolved" section above.)*
14. `update_customer_fields` doesn't validate `balance`/`days_overdue`
    look numeric — consistent with how import-time validation already
    behaves, but worth a decision for manual edits specifically.
15. Search has a flat result cap (20 Mini App / 10 Telegram), no
    pagination — fine at current data volumes.
18. **Security decision, not silently made:** anonymous (no
    `Authorization` header) Mini App API access is still allowed on
    every endpoint except `/export`. Confirmed this pass that the real
    frontend's `getInitData()` only attaches the header when
    `window.Telegram.WebApp.initData` is non-empty at request time —
    it does NOT always send credentials (e.g. if the app is opened
    outside Telegram, or hit before Telegram's WebApp script finishes
    initializing). Removing anonymous access now would risk legitimate
    requests failing on a timing edge case, not just blocking bad
    actors. Recommend: confirm `initData` is reliably populated before
    the first API call fires (e.g. gate the initial fetch on
    `telegram.isReady`) before making auth mandatory.
19. **Real gap, not implemented:** a customer whose every phone number
    is blacklisted is still selectable as current/next — queue
    eligibility only checks the customer-level `is_blacklisted` flag,
    not "does this customer have at least one non-blacklisted phone."
    `first_non_blacklisted_phone()` correctly falls back to *showing*
    the first (blacklisted) number rather than blanking it, but nothing
    skips the customer entirely the way a real "can't actually be
    called" case probably should. Verified live via HTTP, not just
    inspection. Not implementing this now — it's a new business rule
    (what does "uncallable" mean for queue eligibility?) requiring a
    decision, not a bug fix.
20. **Confirmed, exact defect, not silently fixed:** `duration_seconds`
    in `complete_current_session()` is raw wall-clock time from
    `started_at` to `finished_at`, with no pause-awareness and no idle
    detection. A session started, worked briefly, then left open for a
    week before being resumed and finished would report an absurdly
    inflated `average_seconds_per_customer`. Smallest correct fix is
    unclear without a product decision: should idle time simply not
    count (requires tracking active-vs-idle segments), should there be
    an auto-pause-after-inactivity threshold, or should duration be
    capped at some sane maximum? Flagging precisely rather than
    guessing at the right semantics.

### Pre-existing, unrelated to any of this work

16. `test_import_pipeline.py::TestMalformedAndAdversarialInputs::test_bare_scalar_text_is_routed_to_ai_parser_not_json_validation`
    — **status changed, cause not identified.** Previously reconfirmed
    failing across three separate passes. Now passes consistently (3/3
    runs) as of commit `0fea725`, with neither `ai_parser.py`,
    `importer.py`, nor the test itself changed since it was last
    confirmed failing (commit `f91e405`). Most likely explanation is an
    environment/dependency difference rather than a code fix, since
    nothing in the diff touches this path — but that's inference, not
    confirmed. Flagging the discrepancy rather than quietly relabeling it
    "fixed." Worth re-checking if it resurfaces.
17. `test_admin_commands.py` has a pre-existing unused `import sqlite3`.
    Cosmetic, not introduced by any of this work.
