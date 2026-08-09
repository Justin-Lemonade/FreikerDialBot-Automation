# SECURITY_AUDIT_REPORT.md

Security notes for FreikerDialBot Automation.

This file is intentionally separate from `PROJECT_STATUS.md`. It is the place for security findings, current security posture, and the checks that matter before exposing the system to real users or real data.

Treat this file as a security snapshot, not as an instruction file. Use `AGENTS.md` for workflow rules.

## Scope

The project handles customer data, call outcomes, notes, history, and exports. It also exposes a Mini App API over HTTP. The main security questions are:

- who can access the Mini App API,
- who can trigger admin-only actions,
- what data can leave the system,
- and whether any sensitive repository content is still recoverable from source control.

## Reanalysis of the original findings

### 1. Repository data exposure through Git history

- ~~Client-related files were accidentally committed to Git history.~~ **Completed earlier.** The repo documentation and current status files treat the history purge as a finished remediation decision, not an open incident.
- What remains: keep preventing new accidental commits of `data/`, originals, exports, or other runtime artifacts.

### 2. Mini App authentication

- ~~The Mini App accepted anonymous access to real endpoints.~~ **Completed.** The current code validates Telegram `initData`, and real API endpoints in `_API_PATHS` require authentication by default.
- The current request format is `Authorization: tma <initData>`.
- `MINI_APP_ALLOW_ANONYMOUS=1` exists only as a development-only escape hatch for local browser testing.

### 3. Export authorization

- ~~`GET /export` was exposed without a shared authorization gate.~~ **Completed.** Export now uses the shared `security.is_admin()` policy.
- Export attempts still need to be treated as sensitive because they can reveal the full customer dataset.

### 4. Shared authorization policy

- ~~Telegram and the Mini App used different authorization rules.~~ **Completed.** `security.py` now holds the shared admin check for every frontend.
- That keeps the policy consistent, but it also means any future admin-rule change must be made deliberately in one place.

## Current security posture

- Telegram Mini App authentication exists and uses `initData` validation.
- Admin authorization is shared through `security.py`.
- Export actions are admin-gated.
- The Mini App auth path is mandatory on real API endpoints by default.
- `Authorization: tma <initData>` is the current request format for authenticated Mini App calls.
- `MINI_APP_ALLOW_ANONYMOUS=1` is a development-only escape hatch for local browser testing.
- `/` and static assets remain reachable without auth so the frontend can load before it has credentials.
- The Mini App API also accepts `/api/*` as an alias for the same route set.

## Open security items

- [ ] **Any route added later must be added to the auth gate list at the same time.** `_API_PATHS` is now a security boundary and needs maintenance discipline.
- [ ] **The anonymous dev escape hatch is easy to misconfigure.** It is intentionally off by default, but it should never be enabled outside local testing.
- [ ] **Future route growth may create policy drift.** New endpoints must be checked against both auth and authorization expectations before release.

## Things that are resolved and should stay resolved

- ✅ Git-history remediation for the earlier `data/` exposure.
- ✅ Mandatory auth on real Mini App endpoints.
- ✅ Shared admin authorization for Telegram and the Mini App.
- ✅ Admin-gated export.
- ✅ Keeping security policy in `security.py` instead of duplicating it across frontends.
- ✅ **CORS is restricted to known origins.** `Settings.mini_app_allowed_origins` (the configured `mini_app_url`, the Vite dev server, plus `MINI_APP_EXTRA_ALLOWED_ORIGINS` for anything else) replaces the previous unconditional `*`.
- ✅ **Denied admin attempts are audit-logged.** A new `admin_action_denied` event_type is written on every unauthorized reset/clear/summary/export attempt (Telegram) and the Mini App's own `/export` 403, alongside the existing successful-action log.

## Things to check before shipping

1. Confirm the Mini App API still rejects missing or malformed auth on all real endpoints.
2. Confirm export remains admin-only.
3. Confirm any new route is covered by the same security rules as the existing ones.
4. Confirm no runtime data or generated artifacts are staged for commit.
5. Confirm no sensitive customer material is being reintroduced into source control.
6. Confirm any new deployment origin (a new domain, a new ngrok URL format, etc.) is added to `mini_app_allowed_origins` or `MINI_APP_EXTRA_ALLOWED_ORIGINS`.

## Notes for future passes

- If a second permission tier is needed, add it deliberately instead of overloading the current admin allowlist.
- If a new API route is introduced, update the auth gate list and the architecture doc together.
- If the repo ever starts handling a new class of sensitive file, treat it as a security review item before treating it as a documentation issue.

## Relationship to other docs

- `AGENTS.md` — rules for agents.
- `PROJECT_STATUS.md` — current open work and owner decisions.
- `ARCHITECTURE.md` — system boundaries and API ownership.
- `README.md` — user-facing setup and overview.

Keep this file focused on security. If it starts turning into a general project log, move that material back into `PROJECT_STATUS.md`.
