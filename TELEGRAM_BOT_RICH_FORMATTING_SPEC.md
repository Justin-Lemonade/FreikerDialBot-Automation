# Telegram Bot Rich Formatting Specification

## Purpose

Redesign the Telegram bot's text presentation so operational information is significantly easier to scan without changing backend business logic, queue semantics, customer data semantics, or Mini App behavior.

This is a Telegram-side presentation/UX project. It should make the existing bot feel like a deliberate operating console rather than a collection of raw text responses.

## Platform findings

Telegram's current Bot API supports styled text entities and HTML/Markdown formatting, including bold, italic, underline, strikethrough, spoilers, inline code, preformatted code, links, and block quotations. The current Bot API documentation also describes newer Rich Message capabilities including headings, lists, tables, block quotations, collapsible blocks, and other structured blocks. The implementation should not assume the project's installed `python-telegram-bot` version exposes every newest Bot API capability; inspect the installed dependency/API before choosing an implementation.

For this project, **HTML parse mode should be the default presentation layer for ordinary bot messages** unless a concrete technical reason in the repository requires entities or MarkdownV2. HTML is preferred because MarkdownV2 escaping is unnecessarily fragile for customer names, phone numbers, loan values, punctuation, and imported text.

## Design goals

1. Make every important Telegram message scannable in under a few seconds.
2. Establish one consistent visual language across commands and workflows.
3. Make important values visually prominent without excessive decoration.
4. Keep customer data readable on mobile screens.
5. Never expose raw markup to users.
6. Never allow customer/imported text to inject Telegram HTML.
7. Keep messages within Telegram's message-size constraints.
8. Preserve existing inline keyboards and callback behavior.
9. Keep presentation separate from business logic so future UI changes do not require rewriting queue/database logic.
10. Do not redesign the Mini App as part of this task.

## Proposed message language

Use a consistent hierarchy:

- `<b>Section title</b>` for the primary heading.
- `<b>Field:</b> value` for important customer/session fields.
- `<code>...</code>` for identifiers, loan numbers, commands, and values that users may copy exactly.
- Short status labels such as `ACTIVE`, `PAUSED`, `COMPLETED`, `BLACKLISTED`, `NO ANSWER` should be visually distinct but not spammed throughout the message.
- Blank lines separate logical sections.
- Bullets should be used for short lists rather than long runs of punctuation.
- Inline keyboards remain the primary interaction mechanism; formatting should explain buttons, not replace them.

Avoid:

- giant ASCII separators;
- decorative emoji on every line;
- all-caps paragraphs;
- raw JSON unless explicitly requested;
- MarkdownV2 unless technically necessary;
- putting every field on a separate decorative line when a compact layout is clearer;
- duplicating information already represented by buttons.

## Customer message target layout

Customer-facing operational messages should generally follow this structure:

<b>Customer Name</b>
<code>CKT/Loan Number</code>

<b>Contact</b>
• Phone: <code>...</code>
• Alternate: <code>...</code>

<b>Loan</b>
• Outstanding: <b>...</b>
• Monthly payment: <b>...</b>
• Other relevant payment fields when actually available

<b>Status</b>
• Queue position: <b>...</b>
• Last called: <b>...</b>
• Current state: <b>...</b>

Then the existing relevant inline keyboard.

Only render fields that actually exist. Do not manufacture values, use fake placeholders, or imply that unavailable data is zero.

## Queue/status messages

Queue messages should prioritize state and action:

<b>Calling Queue</b>

<b>Progress:</b> 12 / 30
<b>Remaining:</b> 18
<b>Current:</b> Customer Name
<b>Status:</b> ACTIVE

Then the relevant action buttons.

For paused/empty/completed states, explain the state in one or two concise lines and put the next available action in the keyboard.

## Statistics messages

Statistics should use compact sections rather than raw dictionaries or database-shaped output.

Example structure:

<b>Today's Statistics</b>

<b>Calls</b>
• Contacted: <b>...</b>
• No answer: <b>...</b>
• Total: <b>...</b>

<b>Outcomes</b>
• Paid: <b>...</b>
• Promise to pay: <b>...</b>
• Other: <b>...</b>

Only display metrics that are actually supported by the current statistics engine.

## Help/command messages

Replace the current flat command dump with grouped sections:

<b>Calling</b>
• <code>/resume</code> — start/continue queue
• <code>/pause</code> — pause queue
• <code>/status</code> — queue progress

<b>Customers</b>
• <code>/customer</code> — search customer
• <code>/edit</code> — edit customer
• <code>/blacklist</code> — blacklist customer

<b>Session</b>
• <code>/session</code> — current session details
• <code>/rename</code> — rename session
• <code>/stats</code> — statistics

<b>Administration</b>
• restricted commands shown only where appropriate

The exact command set must be derived from the current implementation, not invented by the agent.

## Error messages

Errors should have a predictable structure:

<b>Could not complete that action</b>

Short explanation of what went wrong.

<b>What to do:</b> one concrete next step.

Do not expose tracebacks, internal paths, SQL statements, secrets, raw exceptions, or implementation details to ordinary Telegram users unless the existing authorization/debug behavior explicitly requires it.

## Import/progress messages

Existing progress stages should be formatted consistently and remain concise. Do not turn progress updates into long paragraphs. Where appropriate, use one stable message that is edited rather than repeatedly sending new messages, but only if this fits the current handler architecture and does not introduce unnecessary complexity.

## Long-message handling

Telegram has message-size limits. The implementation must introduce a centralized safe-send/edit helper for formatted text where appropriate.

The helper should:

- escape dynamic values safely for HTML;
- detect oversized messages;
- split only at safe logical boundaries when possible;
- avoid splitting inside HTML tags;
- preserve keyboard behavior correctly;
- avoid duplicating or truncating customer data silently;
- be covered by tests.

Do not solve length problems by simply truncating customer information.

## Security requirement

All dynamic customer/imported/database text must be HTML-escaped before insertion into formatted messages. Formatting tags must originate only from trusted application templates.

Do not allow a customer name such as `<b>...</b>` or imported text containing HTML to alter the message formatting.

## Architecture requirement

Do not scatter formatting strings throughout business logic.

Prefer a small Telegram presentation layer, for example:

- `telegram_formatting.py` / equivalent formatter module;
- reusable formatting helpers for customer, queue, session, statistics, help, and errors;
- a centralized safe-send/safe-edit utility where justified;
- tests focused on escaping, expected formatting, message-size handling, and representative outputs.

Use the repository's existing module structure if a better existing location is already present. Do not create a new abstraction merely to rename existing functions.

## Scope boundaries

This task DOES include:

- Telegram message formatting;
- consistent message hierarchy;
- safe HTML escaping;
- reusable presentation helpers;
- Telegram message-size handling;
- tests for the formatting layer;
- updating affected Telegram-side documentation.

This task DOES NOT include:

- Mini App redesign;
- queue/database redesign;
- customer schema changes;
- authentication redesign;
- changing business rules;
- inventing new customer fields;
- changing call outcome semantics;
- changing command permissions;
- major dependency upgrades;
- adopting the newest Telegram Rich Message API merely because it exists.

## Required implementation process

1. Read `AGENTS.md` and `PROJECT_STATUS.md`.
2. Check the Active Work Registry before claiming files.
3. Audit the current Telegram handlers and locate every major user-facing message family.
4. Identify existing formatting utilities before creating new ones.
5. Identify the installed `python-telegram-bot` version and the formatting APIs it actually exposes.
6. Design the formatter around the current architecture.
7. Implement the smallest maintainable presentation layer.
8. Convert the highest-value Telegram messages first: customer display, queue status, session/status, statistics, help, and errors.
9. Add safe escaping for every dynamic field.
10. Add message-length handling based on actual Telegram constraints.
11. Add focused tests.
12. Run the full relevant test suite and Telegram-focused tests.
13. Review the diff for accidental business-logic changes.
14. Report exactly what was changed and what was intentionally left untouched.

## Acceptance criteria

- Major Telegram messages use a consistent formatting hierarchy.
- Dynamic customer/imported text cannot inject HTML formatting.
- Existing command behavior and callback behavior remain unchanged.
- No business rules are changed.
- No Mini App files are changed unless a shared helper is genuinely required and explicitly justified.
- Long formatted messages are handled safely.
- Tests cover escaping and representative formatting outputs.
- Existing Telegram tests pass.
- Full relevant test suite passes.
- The resulting code is maintainable and centralized rather than a collection of ad-hoc formatted strings.

## Delegation decision

This is a **Telegram-side UX/presentation implementation**. It is appropriate for a capable smaller maintenance model only after the presentation contract above has been accepted. The worker may implement the bounded formatting layer and tests, but ambiguous product decisions, major UI redesigns, backend architecture changes, or changes to customer/queue semantics must be escalated to the Delegation Handler/Claude.
