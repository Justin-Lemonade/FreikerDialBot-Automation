# Work Report — 2026-08-10

## Who did this

This work was performed autonomously by **opencode**, an interactive CLI coding agent, running on the **deepseek-v4-flash-free** model (model ID `opencode/deepseek-v4-flash-free`).

The task was assigned by following the instructions in `PROJECT_STATUS.md`: pick a delegated job that was not in dev (Claude/frontier) territory and not already completed, then finish it and record the result.

## Which job I picked

From the Delegation Control Center in `PROJECT_STATUS.md`, the open, small-model-eligible verification tasks were:
- `VERIFY-013` — importer archive-directory wiring (investigation)
- `VERIFY-014` — API route/documentation parity (review)
- `VERIFY-015` — API auth-boundary coverage after route changes (verification)

I focused on **VERIFY-014** and **VERIFY-015**, which are closely related (both audit the Mini App API against `ARCHITECTURE.md` and the auth gate in `_API_PATHS`). VERIFY-013 was already completed in an earlier commit (`eef21ee`) before I started.

## What I found

1. **`POST /import` was missing from the API documentation.**
   The code already implemented the route (`mini_app_api.py`, handler at `_api_request`, entry in `_API_PATHS`), and `tests/test_mini_app_api.py::TestImportEndpoint` covers it. But `ARCHITECTURE.md`'s route list omitted it. This was the only route/documentation mismatch.

2. **Auth-boundary coverage is complete — every implemented route sits behind the gate.**
   I compared every path dispatched by `_api_request` against the `_API_PATHS` auth set. 100% of handled routes are gated, and every `_API_PATHS` entry has a handler. No mismatch. The `_api_request` auth check fires before method dispatch, so it is path-based and method-independent.

3. **A real pre-existing Windows bug surfaced while running the tests.**
   `tests/test_mini_app_api.py::TestImportEndpoint::test_import_xlsx_inserts_customers` failed. `validation.load_xlsx_rows` opened the workbook with `openpyxl.load_workbook(..., read_only=True)` but never called `close()`. Read-only workbooks hold the file handle open, so the Mini App `/import` handler's `finally` block could not unlink its temp file on Windows (`PermissionError`). This was not caused by my changes; it was an existing latent bug exposed by the Windows run.

## What I changed

All of it is committed (author: repo owner via the commit composer):

- **`ARCHITECTURE.md`** — added `POST /import` to the Mini App API route list and noted that `/import` is not admin-gated (mirrors the Telegram bot's upload handlers) while `/export` is the only admin-gated route. *(VERIFY-014)*
- **`validation.py`** — `load_xlsx_rows` now closes the read-only workbook in both the success and error paths, fixing the temp-file lock that broke `/import`/xlsx on Windows. *(VERIFY-015 fallout fix)*
- **`tests/test_mini_app_api.py`** — added `TestAuthBoundaryCoversAllRoutes`, a parametrized test that asserts every path in `_API_PATHS` returns `401` without credentials. This locks the security boundary to the literal route set so a future route added to `_API_PATHS` without being placed behind the gate fails loudly. *(VERIFY-015)*
- **`PROJECT_STATUS.md`** — marked VERIFY-014 and VERIFY-015 as **COMPLETED** with evidence, added the completed items to the "Recently completed / already handled" section, updated the recommended-actions and verification-only queue, and appended the work to the delegation-audit metadata.

## Verification

- Full backend suite: `pytest tests/ -q` → **388 passed** (includes the previously failing xlsx test and the new auth-boundary test).
- Reviewed `git status` and `git diff` — clean tree, no runtime/generated data or secrets introduced.
- Changes are committed locally and the branch is ahead of `origin/main`; no push was made (not requested).

## Boundaries respected

- No product/architecture decisions were invented; VERIFY-012-style security design was not touched.
- The xlsx fix is the smallest correct change in the importer, not a redesign.
- No new non-canonical files beyond this report were added to the repo.