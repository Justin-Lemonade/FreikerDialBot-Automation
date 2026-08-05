# Delegation Tasks

Self-contained specs for the highest-value items in `BACKLOG.md`'s
"Still open" list that don't require a product decision first — each one
should be pickable up by a session with zero other context beyond this
file, `AGENTS.md`, and the file(s) named below. Written 2026-08-05, after
the priority security pass, against commit `2de2386`.

Items that aren't here because they need *your* decision, not more
investigation, are listed at the bottom instead.

---

## Task 1: Restrict CORS to the real Mini App origin

**Why:** `Access-Control-Allow-Origin: *` is wide open on every Mini App
API response. Low practical risk today (auth isn't cookie-based, so a
malicious page still can't forge a valid `initData` signature just by
getting a browser to send a cross-origin request) — but it's a one-line
hardening step now that auth is mandatory by default, and free.

**Where:** `mini_app_api.py`, 4 call sites currently hardcode `"*"`:
`_json()`, `_file()`, and two more in the static-file-serving path (grep
`Access-Control-Allow-Origin` to find all four — don't rely on this
count staying accurate, re-check).

**What to do:**
1. Use `self.service.settings.mini_app_url` as the allowed origin
   instead of `"*"`. It's already populated — either from an explicit
   `MINI_APP_URL` env var or the discovered ngrok tunnel URL, falling
   back to `http://{host}:{port}` (see `config.py` and
   `start_mini_app.py`'s `launch_mini_app_stack()`).
2. Decide what happens when `mini_app_url` is the local fallback (i.e.
   no real deployed origin yet, e.g. running `mini_app_api.py` directly
   for local dev) — probably just use whatever `mini_app_url` resolved
   to either way, since local dev already only serves one origin.
3. Centralize this rather than repeating the lookup 4 times — a small
   helper method on `MiniAppRequestHandler` (or a `service` property)
   that all 4 call sites use.

**Acceptance criteria:**
- A request from the real Mini App origin still gets CORS headers that
  work.
- A request with a different `Origin` header no longer gets
  `Access-Control-Allow-Origin: *` back.
- Existing tests in `test_mini_app_api.py`/`test_mini_app_routing.py`
  still pass; add at least one asserting the header value matches
  `settings.mini_app_url`, not `*`.

**Effort:** Low.

---

## Task 2: Audit-log denied admin attempts, not just successful ones

**Why:** `admin_action` events are written on every successful
reset/clear/export (`_record_admin_action()` in `admin_commands.py`,
same pattern in `mini_app_api.py`'s `/export` handler). A *denied*
attempt currently leaves no trace at all — if someone probes for admin
access, there's nothing to detect it by.

**Where:** `security.py`'s `is_admin()` is the single choke point both
frontends already call before an admin action; `admin_commands.py`'s
`_record_admin_action()` is the existing event-writing pattern to
extend, not replace.

**What to do:**
1. Add a call to record a `admin_action_denied` (or similar — pick a
   type that's clearly distinct from `admin_action` in the event log,
   not a variant that could be confused with a successful one) event at
   each of the call sites that currently check `is_admin()` and reject
   — both Telegram's admin commands and the Mini App's `/export`.
2. Decide what to attribute it to: the rejected `telegram_user_id` if
   one was resolved (i.e. valid Telegram identity, just not an admin),
   or explicitly log "no identity" separately from "identified but not
   admin" — these are different signals for detecting abuse and
   shouldn't be conflated.
3. This changes log volume — a chatty/bot-probed endpoint could write a
   lot of denial events. Consider whether that's fine as-is or needs
   rate-limiting/dedup later; don't over-engineer this pass, just don't
   make it silently unbounded without noting it.

**Acceptance criteria:**
- A non-admin Telegram user attempting an admin command produces a
  logged event, verifiable via `Database.get_customer_events` or
  equivalent (this isn't customer-scoped, so check where non-customer
  admin events currently land in the schema before assuming
  `customer_events` is the right table — `record_event()` in
  `statistics_engine.py` may not require a customer_id, confirm rather
  than assume).
- Same for a non-admin `/export` attempt via the Mini App.
- A genuinely successful admin action still only produces the existing
  `admin_action` event, not both.

**Effort:** Low-medium (mostly in deciding the exact event shape, not
the code).

---

## Task 3: Add `POST /queue/resume` to the Mini App API

**Why:** `QueueEngine.resume()` is fully implemented and already used by
Telegram's queue handlers — it's just never been wired up as a Mini App
route. `/queue/pause` exists; `/queue/resume` doesn't. This is a gap,
not a design decision — the backend logic is already there and tested.

**Where:**
- `queue_engine.py`'s `resume()` — already does everything needed
  (sets `session_start_time` if this is the first resume, flips
  `is_paused`, resumes the session-manager's current session, returns
  the next customer via `next_customer()`).
- `mini_app_api.py` — model the new route directly on the existing
  `/queue/pause` handler:
  ```python
  if path == "/queue/pause" and method == "POST":
      self._json(200, self.service.pause_queue(telegram_user_id=telegram_user_id))
      return True
  ```
  and `MiniAppService.pause_queue()`:
  ```python
  def pause_queue(self, telegram_user_id: int | None = None) -> dict[str, Any]:
      self.queue_engine.pause(telegram_user_id=telegram_user_id)
      return {"ok": True, "paused": True}
  ```

**What to do:**
1. Add `MiniAppService.resume_queue()`, calling `self.queue_engine.resume(telegram_user_id=telegram_user_id)`.
   Decide what the response payload should include — `resume()` returns
   a `QueueSelection` (the next customer), so this probably wants to
   return more than `{"ok": True}`, likely something shaped like
   `/session/next`'s response. Check what the frontend would actually
   need before picking the shape, don't guess.
2. Add the route in `_api_request` (and to `_API_PATHS` in the same
   file — the auth gate added in this pass enumerates real routes
   explicitly, a new route not added there would silently bypass the
   auth requirement, not silently fail loudly, so this step isn't
   optional).
3. Add it to `frontend/src/api/client.ts` and wherever the "paused"
   state's resume action should trigger it (there's presumably a paused
   UI state already, given `/queue/pause` exists — check
   `Home.tsx`/`ProgressHeader.tsx` for how pause is currently
   surfaced before adding resume next to it).

**Acceptance criteria:**
- `POST /queue/resume` with valid auth resumes a paused queue and
  returns the next customer.
- It's included in `_API_PATHS` and confirmed to 401 without auth (add
  a test following the existing pattern in `test_mini_app_api.py`).
- Frontend can actually trigger it from wherever pause's counterpart
  belongs in the UI.

**Effort:** Low (backend logic already exists; this is routing +
frontend wiring).

---

## Not delegated — need your decision first, not more investigation

These come up as coding tasks but each one is blocked on a product
decision, not a technical gap. Turning any of these into a task spec
without that decision first would mean an agent inventing the business
rule, which this project's own rules (`AGENTS.md`) say not to do.

- **"Paid" outcome has no real write path anywhere** (`BACKLOG.md` #9).
  Needs: a real `QueueEngine.apply_action` status, plus deciding whether
  Telegram gets a matching button or stays without one. The Mini App's
  Paid button is currently disabled with an honest "not yet available"
  state rather than faking it — that's the right interim state, not a
  bug to rush past.
- **Uncallable customers still enter the queue** (`BACKLOG.md` #19) — a
  customer whose *every* phone number is blacklisted is still
  selectable. Needs: a definition of what "uncallable" means for queue
  eligibility (skip entirely? flag but still show? something else?).
- **`duration_seconds` has no idle-awareness** (`BACKLOG.md` #20) — raw
  wall-clock time, so a session left open overnight inflates
  `average_seconds_per_customer`. Needs: a decision on whether idle
  time should just not count (requires tracking active/idle segments),
  an auto-pause-after-inactivity threshold, or a sane cap — three
  different fixes with different amounts of work behind them.
