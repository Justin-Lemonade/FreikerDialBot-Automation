# Freikerr Calling Bot Automation

A complete Telegram-based customer calling automation system. Import customer lists from screenshots, pasted text, JSON, or Excel files — the system normalizes, validates, and queues them for calling. Track progress with real-time statistics, pause/resume calling workflow, and export results in multiple formats.

**Features:**
- 📷 **Multi-format imports**: CRM screenshots, pasted text, JSON arrays, or Excel (.xlsx) files
- 🤖 **AI-powered OCR** with automatic failover to multiple LLM providers (OpenAI, Gemini, GitHub, OpenRouter, Groq, DeepSeek)
- ☎️ **Smart calling queue**: Deterministic queue engine presents customers one at a time, tracks operator actions (warned, call later, skip, paid, invalid number, needs review)
- 📊 **Real-time statistics**: Daily and lifetime call metrics, session tracking, event history
- 📤 **Multiple export formats**: CSV, JSON, Excel (.xlsx)
- 🛡️ **Authorization-gated admin commands**: Reset, clear, summary, export with Telegram user ID allowlisting
- 🌐 **Mini App API**: HTTP endpoint for third-party integrations

## Quick Start

### Prerequisites

- Python 3.12 or newer
- Telegram Bot API token (get one from [@BotFather](https://t.me/BotFather))
- At least one AI provider API key (OpenAI, Gemini, GitHub Models, or others)

### Installation

1. Clone and navigate to the project:

   ```bash
   cd "FreikerDialBot Automation"
   ```

2. Create a virtual environment:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # or: source .venv/bin/activate  # macOS/Linux
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Configure `.env`:

   ```env
   # Required
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   OPENAI_API_KEY=your_openai_key_here

   # Optional: Admin User IDs (comma-separated Telegram numeric IDs)
   ADMIN_TELEGRAM_USER_IDS=123456789,987654321

   # Optional: AI Provider Failover (at least one primary key above, or one from below)
   GEMINI_API_KEY=your_gemini_key_here
   GEMINI_MODEL=gemini-2.5-flash

   GITHUB_TOKEN=your_github_token_here
   GITHUB_MODEL=gpt-4o

   OPENROUTER_API_KEY=your_openrouter_key_here
   OPENROUTER_MODEL=openrouter/free

   GROQ_API_KEY=your_groq_key_here
   GROQ_MODEL=llama-3.3-70b-versatile

   DEEPSEEK_API_KEY=your_deepseek_key_here
   DEEPSEEK_MODEL=deepseek-chat
   ```

   If no API key is provided, screenshot OCR will be disabled — text and JSON imports will still work.

5. Run the bot:

   ```bash
   python bot.py
   ```

   This single command now brings up the entire stack: it builds the
   Mini App frontend, starts its backend API, starts an ngrok tunnel to
   it (if ngrok is installed and configured), and then starts the
   Telegram bot itself with the discovered Mini App URL already set --
   no separate launcher script or manual URL copying needed.

   - If ngrok isn't installed, the bot still starts normally; the Mini
     App backend runs locally but has no externally-reachable URL yet
     (set `MINI_APP_URL` manually in `.env` if you're exposing it another
     way). See [ngrok's download page](https://ngrok.com/download) and
     run `ngrok config add-authtoken <token>` once to enable this.
   - To run the bot without the Mini App stack at all (e.g. no Node.js
     available, or you only want the Telegram bot), use
     `python bot.py --no-mini-app` or set `DISABLE_MINI_APP=1`.
   - `python start_mini_app.py` still works as before if you want the
     Mini App stack (frontend + backend + tunnel) without starting the
     bot -- useful for frontend development.

## Usage

### Importing Customers

Send any of these without needing a `/upload` command first:

- 📷 **Screenshot**: Upload a CRM screenshot image — the AI extracts all visible customer records
- 📋 **Pasted Text**: Paste customer data as text (comma-separated, tab-separated, or formatted)
- 📄 **JSON File**: Upload a `.json` file containing an array of customer objects (no Telegram message length limit)
- 📊 **Excel File**: Upload a `.xlsx` file with customer data (first sheet is used; column names are auto-detected)

The system validates each record and flags incomplete entries (missing name or phone) for manual review. Invalid rows are dropped and reported.

### Commands

#### General Commands

- `/start` — Show current status and quick action buttons
- `/upload` — Reminder of import options (usually not needed)
- `/resume` — Start or continue the calling queue
- `/pause` — Pause the calling queue (can resume later)
- `/status` — Show queue progress (remaining, contacted, did not answer)
- `/session` — Show current calling session details
- `/rename <name>` — Give the current session a custom name (e.g., `/rename Morning Batch`)
- `/stats` — Show today's and lifetime statistics
- `/help` — List all available commands

#### Administrative Commands (authorized users only)

These require the sender's Telegram user ID to be in `ADMIN_TELEGRAM_USER_IDS`.

- `/summary` — Full session summary with completion details, elapsed time, and status breakdown
- `/reset` — Reset all customers back to `waiting` and clear queue position/progress (same import can run again; history preserved)
- `/clear` — Delete all customers and queues (logs, events, statistics, and original imports are preserved)
- `/export [csv|json|xlsx]` — Export all customer records to a timestamped file in `data/exports/` (CSV, JSON, or XLSX format)

## Customer Status Lifecycle

Customers progress through these statuses:

1. **waiting** — Ready to be called
2. **warned** — Operator warned the customer (can be called later)
3. **call_later** — Contact attempt unsuccessful; will retry
4. **skip** — Intentionally skipped in this session
5. **paid** — Account was paid
6. **invalid_number** — Phone number is incorrect or non-existent
7. **needs_review** — Incomplete record (missing name or phone); requires manual review
8. *Removed* — No loan_number (duplicate or malformed) — never inserted into queue

## Data Schema

### Standard Customer Object

Every import is normalized to:

```json
{
  "loan_number": "ABC-12345",
  "first_name": "John",
  "last_name": "Doe",
  "phone_numbers": ["+15551234567"],
  "balance": "1500.00",
  "days_overdue": "30"
}
```

All fields are strings except `phone_numbers`, which is an array. Missing values are empty strings or empty arrays.

### Export Fields

Exports include: Loan Number, First Name, Last Name, Phone Numbers, Balance, Days Overdue, Final Status, Status Timestamp, Session ID.

## Architecture

### Core Modules

- **bot.py** — Telegram bot entry point; integrates all submodules
- **ai_parser.py** — AI-powered OCR with failover routing; supports text and screenshot imports
- **importer.py** — Orchestrates import pipeline: parse → validate → normalize → store
- **database.py** — SQLite database management (customers, sessions, events, statistics)
- **queue_engine.py** — Deterministic queue (presents one customer at a time; tracks operator actions)
- **session_manager.py** — Session lifecycle management (start, pause, resume, complete)
- **statistics_engine.py** — Event-driven statistics tracking (daily and lifetime metrics)
- **export_engine.py** — Modular export registry; supports CSV, JSON, XLSX (extensible for new formats)
- **admin_commands.py** — Authorization-gated admin endpoints
- **telegram_ui.py** — Telegram message handlers and inline keyboards
- **queue_ui.py** — Queue presentation and operator interaction UI
- **stats_ui.py** — Statistics and session summary rendering
- **mini_app_api.py** — HTTP API for Telegram Mini App or third-party integrations
- **validation.py** — Import validation and normalization
- **logger.py** — Structured logging to `data/logs/`
- **config.py** — Environment variable loading and application configuration

### File Structure

```
data/
  ├─ imports/          # Normalized customer JSON after validation
  ├─ originals/        # Original CRM screenshots, pasted text, or files
  ├─ exports/          # CSV, JSON, XLSX exports (timestamped)
  ├─ logs/             # Structured event logs
  └─ session.db        # SQLite database
```

## AI Provider Configuration

The system uses a **failover router** that automatically tries the next provider if one fails. Configure as many or as few as you need:

| Provider | Vision Support | Speed | Model |
|----------|---|---|---|
| OpenAI | ✅ | Good | gpt-4o-mini (default) |
| Google Gemini | ✅ | Fast | gemini-2.5-flash (default) |
| GitHub Models | ✅ | Fast | gpt-4o (default) |
| OpenRouter | ✅ | Varies | openrouter/free (default) |
| Groq | ❌ | ⚡ Fastest | llama-3.3-70b-versatile (default) |
| DeepSeek | ❌ | Good | deepseek-chat (default) |

**Note:** Vision-capable providers (those with ✅) are required for screenshot OCR. Text and JSON imports don't require any AI provider.

## JSON Import Format

For long customer lists, upload a `.json` file to avoid Telegram's 4096-character message limit:

```json
[
  {
    "loan_number": "LN-001",
    "first_name": "Alice",
    "last_name": "Smith",
    "phone_numbers": ["+15551234567"],
    "balance": "2500.00",
    "days_overdue": "45"
  },
  {
    "loan_number": "LN-002",
    "first_name": "Bob",
    "last_name": "Johnson",
    "phone_numbers": ["+15559876543", "+15559999999"],
    "balance": "800.00",
    "days_overdue": "10"
  }
]
```

## Excel Import Format

Upload a `.xlsx` file with these column headers (case-insensitive, aliases supported):

| Primary | Aliases |
|---------|---------|
| loan_number | Loan Number, Loan#, Loan ID, Account Number, Account# |
| first_name | First Name, FirstName |
| last_name | Last Name, LastName, Surname |
| phone_numbers | Phone, Phone Number, Phone Numbers, Mobile, Cell, Telephone |
| balance | Balance, Balance Owed, Amount Owed, Outstanding Balance |
| days_overdue | Days Overdue |

## Testing

Run the test suite:

```bash
pytest
```

Tests are in the `tests/` directory.

## Logging

Structured logs are written to `data/logs/` in JSON format, including:
- Import events (method, count, errors, success status)
- Queue events (customer selection, status changes, pause/resume)
- Session lifecycle events (start, complete, statistics)

## Troubleshooting

### "TELEGRAM_BOT_TOKEN is invalid"
- Double-check your token in `.env` — copy it directly from [@BotFather](https://t.me/BotFather)
- Ensure no leading/trailing spaces

### "OPENAI_API_KEY is required to parse unstructured text"
- Screenshot OCR requires at least one vision-capable AI provider (OpenAI, Gemini, GitHub, or OpenRouter)
- Text and JSON imports work without any API key

### "All available AI providers failed"
- Check API keys in `.env` — verify they're valid and have sufficient quota
- Ensure the API services are not rate-limited or down
- Text imports will still work even if all providers fail

### "No customer list loaded"
- Import customers first: send a screenshot, paste text, or upload a JSON/Excel file
- Use `/status` to see queue progress after import

## Contributing

This project intentionally focuses on the core calling automation workflow. New features should align with:
1. Deterministic queue behavior (same customer order on restart)
2. Stateless operator actions (each action is recorded immutably)
3. Multi-format import flexibility
4. Admin authorization and audit trails

## License

[Add your license here]
