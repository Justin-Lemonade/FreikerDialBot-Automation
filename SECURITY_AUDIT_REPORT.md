# SECURITY_AUDIT_REPORT.md

Security notes for FreikerDialBot Automation.

This file is intentionally separate from `PROJECT_STATUS.md`. It is the place for security findings, current security posture, and the checks that matter before exposing the system to real users or real data.

## Scope

The project handles customer data, call outcomes, notes, history, and exports. It also exposes a Mini App API over HTTP. The main security questions are:

- who can access the Mini App API,
- who can trigger admin-only actions,
- what data can leave the system,
- and whether any sensitive repository content is still recoverable from source control.

## Current security posture

- Telegram Mini App authentication exists and uses `initData` validation.
- Admin authorization is shared through `security.py`.
- Export actions are admin-gated.
- The Mini App auth path is mandatory on real API endpoints by default.
- `Authorization: tma <initData>` is the current request format for authenticated Mini App calls.
- `MINI_APP_ALLOW_ANONYMOUS=1` is a development-only escape hatch for local browser testing.

## Open security items

- CORS is still wide open and should be restricted to the real Mini App origin.
- Denied admin attempts are not yet audit-logged.
- Any route added later must be added to the auth gate list at the same time.
- The repo should continue to avoid recreating temporary files or parallel docs that might accidentally repeat sensitive context.

## Things to check before shipping

1. Confirm the Mini App API still rejects missing or malformed auth on all real endpoints.
2. Confirm export remains admin-only.
3. Confirm any new route is covered by the same security rules as the existing ones.
4. Confirm no runtime data or generated artifacts are staged for commit.
5. Confirm no sensitive customer material is being reintroduced into source control.

## Notes for future passes

- If a second permission tier is needed, add it deliberately instead of overloading the current admin allowlist.
- If denied admin attempts become important operationally, add explicit audit logging rather than assuming the current success-only log is enough.
- If the Mini App origin becomes stable, tighten CORS to that origin instead of leaving it as `*`.
- This file is a security snapshot, not an instruction file; use `AGENTS.md` for workflow rules.

## Relationship to other docs

- `AGENTS.md` — rules for agents.
- `PROJECT_STATUS.md` — current open work and owner decisions.
- `ARCHITECTURE.md` — system boundaries and API ownership.
- `README.md` — user-facing setup and overview.

Keep this file focused on security. If it starts turning into a general project log, move that material back into `PROJECT_STATUS.md`.
