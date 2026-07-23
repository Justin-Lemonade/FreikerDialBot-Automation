# FreikerDialBot Automation Project Instructions

# FreikerDialBot Automation Project Instructions

> **See `AGENTS.md` for canonical architecture, source-of-truth rules, and
> validation commands.** This file keeps only Gemini-specific workflow
> commands (`/implement` and `/test` below) to avoid duplicating content
> that now lives in `AGENTS.md`.

---
## /implement command for New Files

When new files are provided in the `New FIles` directory, they should be integrated into the project by following these steps:
1.  Take the files from `New FIles`.
2.  Implement them by replacing their old versions and sorting them into their respected places.
3.  At the end run all of the tests to make sure that everything is working.

## /test command

You are working in an existing codebase. Your task is to test, fix, verify, and repeat until the repository is stable.

Follow this process exactly:

1. Run the full test suite first.
2. Record every failure you find.
3. Group failures by root cause where possible, but fix them one at a time.
4. For each individual fix:

   * Make the smallest safe change possible.
   * Re-run the most relevant test(s) for that specific failure.
   * If the targeted test still fails, continue iterating on that same issue until it passes.
5. After the targeted test passes, move to the next failure.
6. Repeat this cycle until all identified failures are fixed.
7. Then run the full test suite again.
8. If new failures appear, repeat the same process.
9. Stop only when the full test suite passes, or when you have a clear blocker that cannot be solved without additional information.

Rules:

* Do not change unrelated code unless it is necessary to fix the current failure.
* Do not batch many unrelated fixes together.
* Prefer minimal, maintainable fixes over clever ones.
* Preserve existing behavior unless a test or bug clearly requires a change.
* If a failure appears to be caused by the test itself rather than the code, verify that carefully before editing anything.
* If a fix changes public behavior, confirm whether existing tests should be updated or whether code should be adjusted instead.
* Keep a clear mental map of which failure you are working on and what evidence supports your fix.

When reporting progress, use this format:

* Full test run result:
* Failures found:
* Fix applied:
* Targeted test(s) rerun:
* Result:
* Next issue:
* Final status:

At the end, provide a brief fix report that includes:

* What was broken
* What you changed
* Which tests were run
* Whether everything passes now
* Any remaining risks or known limitations

Work methodically and do not stop after the first success. Continue until the suite is clean.
