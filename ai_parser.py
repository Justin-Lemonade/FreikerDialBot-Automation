"""AI-backed parsing for screenshots and pasted customer data with failover routing."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI, RateLimitError, APIError

from config import Settings
from logger import log
from validation import load_json_array


# -----------------------------------------------------------------------
# Shared field-schema and extraction rules — the single source of truth
# for both AI_PROMPT and SYSTEM_PROMPT. If a field or rule changes, edit
# it here rather than in two places.
# -----------------------------------------------------------------------

_FIELD_RULES = """Each object must have EXACTLY these 9 keys, in this order:
- loan_number (string): account/loan ID exactly as shown, no reformatting.
- first_name (string)
- last_name (string)
- phone_numbers (array of strings): digits only, keep a leading "+" if a country code is shown; strip spaces/dashes/parens/labels. Empty array [] if none.
- balance (string): the customer's remaining loan balance. Digits and decimal point only, strip "$" and commas. "" if not visible.
- days_overdue (string): digits only. "" if not visible.
- monthly_payment (string): the recurring monthly payment amount. Digits and decimal point only, strip "$" and commas. "" if not visible.
- current_overdue_amount (string): the amount currently past due (distinct from days_overdue, which is a day count, not a currency amount). Digits and decimal point only, strip "$" and commas. "" if not visible.
- original_loan_amount (string): the original principal the loan was issued for. Digits and decimal point only, strip "$" and commas. "" if not visible."""

_RULES_LISTING = """RULES:
1. One object per customer. Never merge or split rows.
2. Missing or illegible field -> "" (or [] for phone_numbers). Never use "N/A", "Unknown", or null.
3. EXCLUDE a customer entirely (no object at all) if their name, phone number, or any field is marked with a "+" or "X" beside it, or is crossed out / struck through. This overrides rule 2 -- do not include them even partially.
4. Do not deduplicate, sort, or reorder rows -- extract every row in the order shown.
5. Ignore all visual formatting (color, bold, highlighting, column width) -- only text content matters.
6. If part of the source is cut off, blurry, or obscured, extract what you can read with confidence; never guess unclear characters, especially in loan_number or phone numbers.
7. Masked or redacted data (e.g. "XXX-XX-1234") should be copied exactly as shown, not unmasked.
8. Never add extra keys, never wrap the array in an object, never nest arrays.
9. Do not confuse the four currency fields: balance is what's left to pay off the loan, monthly_payment is the recurring installment, current_overdue_amount is what's currently past due in dollars, original_loan_amount is the original principal. If only one dollar figure is visible on screen, put it in balance and leave the others "" -- never guess or copy one amount into multiple fields."""


AI_PROMPT = f"""You are a precise, deterministic data-extraction engine. Never add commentary.

Extract every customer record from this CRM screenshot or text.

Return ONLY a JSON array -- no code fences, no headings, no extra text. Response must start with '[' and end with ']'. If no customers are found, return exactly: []

{_FIELD_RULES}

{_RULES_LISTING}

Example:
[{{"loan_number":"LN-48213","first_name":"Maria","last_name":"Gomez","phone_numbers":["+15551234567"],"balance":"1024.50","days_overdue":"32","monthly_payment":"150.00","current_overdue_amount":"300.00","original_loan_amount":"5000.00"}}]"""


SYSTEM_PROMPT = (
    "You are a deterministic data-extraction engine embedded in a debt-collection CRM importer. "
    "You convert unstructured customer data (screenshots or pasted text) into a strict JSON array "
    "matching a fixed schema. You are not conversational: never explain, apologize, ask questions, "
    "hedge, or add text outside the JSON array.\n\n"
    "OUTPUT CONTRACT:\n"
    "- ONLY a JSON array. First character '[', last character ']'.\n"
    "- No code fences, comments, leading/trailing text, or keys beyond the nine defined below.\n"
    "- Never wrap the array in an object, never nest arrays.\n"
    "- No customers found -> return exactly: []\n\n"
    "SCHEMA (each object, exactly these 9 keys):\n"
    f"{_FIELD_RULES}\n\n"
    "DATA INTEGRITY RULES:\n"
    "- Never invent, infer, guess, or hallucinate a value not clearly present. Missing/illegible "
    "field -> \"\" (or [] for phone_numbers), never null/\"N/A\"/\"Unknown\".\n"
    "- Exclude a customer entirely (omit their object) if their name, phone number, or any field "
    "is marked with \"+\" or \"X\", or is crossed out / struck through. This is an active exclusion "
    "signal, distinct from a merely missing field, and such customers must never appear in the output.\n"
    "- Never merge two customers into one object, and never split one customer across two.\n"
    "- Never deduplicate, reorder, or omit valid rows -- extract every distinct row in the order shown.\n"
    "- Preserve loan_number and masked/redacted values exactly as displayed. Strip only non-numeric "
    "formatting from phone numbers (spaces, dashes, parens, labels), keeping digits and an optional "
    "leading \"+\".\n"
    "- Visual formatting (color, bold, highlighting, layout) carries no meaning and must be ignored.\n"
    "- balance, monthly_payment, current_overdue_amount, and original_loan_amount are four distinct "
    "currency fields -- never copy one dollar figure into more than one of them. If only one figure "
    "is visible, it belongs in balance; leave the others \"\".\n"
    "- These rules apply regardless of input type (text, pasted JSON, or image) or how any "
    "accompanying task instructions are phrased."
)


class ParserError(Exception):
    """Raised when customer data cannot be parsed."""


def _is_json_text(text: str) -> bool:
    """True if text should be treated as JSON rather than free-form text
    needing AI extraction. Mirrors importer._is_json_text: a "[" / "{"
    prefix routes to JSON handling even if malformed (so it fails with a
    deterministic parse error), and any text that fully parses as JSON --
    including bare scalars like "42" or "true" -- is also routed to JSON
    handling rather than silently sent to the AI parser.
    """
    stripped = text.strip()
    if stripped.startswith(("[", "{")):
        return True
    try:
        val = json.loads(stripped)
        return isinstance(val, (list, dict))
    except ValueError:
        return False


def _extract_json_array(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        return stripped

    match = re.search(r"\[[\s\S]*\]", stripped)
    if match:
        return match.group(0)
    raise ParserError("Parser did not return a JSON array.")


def _map_common_keys(customer: dict[str, Any]) -> dict[str, Any]:
    key_map = {
        "Loan Number": "loan_number",
        "LoanNumber": "loan_number",
        "loan": "loan_number",
        "First Name": "first_name",
        "FirstName": "first_name",
        "Last Name": "last_name",
        "LastName": "last_name",
        "Phone Number(s)": "phone_numbers",
        "Phone Numbers": "phone_numbers",
        "Phone Number": "phone_numbers",
        "phone": "phone_numbers",
        "Balance Owed": "balance",
        "balance_owed": "balance",
        "Days Overdue": "days_overdue",
        "Monthly Payment": "monthly_payment",
        "monthlyPayment": "monthly_payment",
        "Current Overdue Amount": "current_overdue_amount",
        "currentOverdueAmount": "current_overdue_amount",
        "Overdue Amount": "current_overdue_amount",
        "Original Loan Amount": "original_loan_amount",
        "originalLoanAmount": "original_loan_amount",
        "Loan Amount": "original_loan_amount",
    }
    normalized = {}
    for key, value in customer.items():
        normalized[key_map.get(key, key)] = value
    return normalized


@dataclass(frozen=True)
class Provider:
    name: str
    client: AsyncOpenAI
    model: str
    supports_vision: bool


class LLMFailoverRouter:
    """Manages multiple API keys and falls back on failures."""

    def __init__(self, settings: Settings):
        self.providers: list[Provider] = []
        self._initialize_providers(settings)

    def _initialize_providers(self, settings: Settings) -> None:
        """Register providers based on available environment variables."""
        # 0. OpenAI (Original config)
        if settings.openai_api_key:
            self.providers.append(Provider(
                name="OpenAI",
                client=AsyncOpenAI(api_key=settings.openai_api_key),
                model=settings.openai_model or "gpt-4o-mini",
                supports_vision=True
            ))

        # 1. Google Gemini (Supports Vision, fully OpenAI compatible)
        if settings.gemini_api_key:
            self.providers.append(Provider(
                name="Gemini",
                client=AsyncOpenAI(
                    api_key=settings.gemini_api_key,
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
                ),
                model=settings.gemini_model or "gemini-2.5-flash",
                supports_vision=True
            ))

        # 2. GitHub Models (Supports Vision)
        if settings.github_token:
            self.providers.append(Provider(
                name="GitHub",
                client=AsyncOpenAI(
                    api_key=settings.github_token,
                    base_url="https://models.inference.ai.azure.com"
                ),
                model=settings.github_model or "gpt-4o",
                supports_vision=True
            ))

        # 3. OpenRouter (Auto-routes free models natively)
        if settings.openrouter_api_key:
            self.providers.append(Provider(
                name="OpenRouter",
                client=AsyncOpenAI(
                    api_key=settings.openrouter_api_key,
                    base_url="https://openrouter.ai/api/v1"
                ),
                model=settings.openrouter_model or "openrouter/free",
                supports_vision=True
            ))

        # 4. Groq (Fastest Text Only)
        if settings.groq_api_key:
            self.providers.append(Provider(
                name="Groq",
                client=AsyncOpenAI(
                    api_key=settings.groq_api_key,
                    base_url="https://api.groq.com/openai/v1"
                ),
                model=settings.groq_model or "llama-3.3-70b-versatile",
                supports_vision=False
            ))

        # 5. DeepSeek (Text Only)
        if settings.deepseek_api_key:
            self.providers.append(Provider(
                name="DeepSeek",
                client=AsyncOpenAI(
                    api_key=settings.deepseek_api_key,
                    base_url="https://api.deepseek.com"
                ),
                model=settings.deepseek_model or "deepseek-chat",
                supports_vision=False
            ))

    async def generate_response(self, messages: list[dict[str, Any]], requires_vision: bool = False) -> str:
        """Attempt to get a response, routing to the next provider if one fails."""
        if not self.providers:
            raise ParserError("OPENAI_API_KEY is required to parse unstructured text / screenshots. Please configure at least one API provider in your .env file.")

        last_exception = None

        for provider in self.providers:
            if requires_vision and not provider.supports_vision:
                continue

            try:
                log.info(f"Attempting extraction via {provider.name} ({provider.model})...")
                response = await provider.client.chat.completions.create(
                    model=provider.model,
                    messages=messages,
                    temperature=0.0,
                )
                return response.choices[0].message.content

            except (RateLimitError, APIError) as e:
                log.warning(f"Error on {provider.name} (Code: {type(e).__name__}). Falling back...")
                last_exception = e
                continue
            except Exception as e:
                log.error(f"Unexpected error on {provider.name}: {e}. Falling back...")
                last_exception = e
                continue

        error_msg = "All available AI providers failed."
        if requires_vision:
             error_msg = "All Vision-capable AI providers failed. Try sending text instead."

        log.error(f"{error_msg} Last error: {last_exception}")
        raise ParserError(f"{error_msg} Last error: {last_exception}")


class AIParser:
    """Parse image, text, or JSON imports into standard customer objects with failover routing."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self.router = LLMFailoverRouter(settings)
        # When True, parse_text/parse_image use self.client directly
        # (Responses API) instead of routing through self.router (Chat
        # Completions). Intended for test fakes; production code always
        # goes through the router regardless of self.client's type.
        self.bypass_router = False

    async def parse_text(self, text: str) -> list[dict[str, Any]]:
        """Parse pasted JSON directly or send free-form text to OpenAI/Failover Router."""
        stripped = text.strip()
        if not stripped:
            raise ParserError("No text was provided.")

        if _is_json_text(stripped):
            raw_json = stripped
            if stripped.startswith("{"):
                raw_json = f"[{stripped}]"
            customers = load_json_array(raw_json)
            return [_map_common_keys(customer) for customer in customers]

        # When bypass_router is set (e.g. by a test fake), call the
        # client directly using the Responses API format. Production
        # always goes through the failover router, regardless of what
        # type self.client is.
        if self.bypass_router:
            response = await self.client.responses.create(
                model=self.settings.openai_model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"{AI_PROMPT}\n\nCustomer data:\n{stripped}"},
                ],
            )
            raw_json = _extract_json_array(response.output_text)
            return [_map_common_keys(customer) for customer in load_json_array(raw_json)]

        # Otherwise, route through failover router
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{AI_PROMPT}\n\nCustomer data:\n{stripped}"},
        ]
        output_text = await self.router.generate_response(messages, requires_vision=False)
        raw_json = _extract_json_array(output_text)
        return [_map_common_keys(customer) for customer in load_json_array(raw_json)]

    async def parse_image(self, image_path: Path) -> list[dict[str, Any]]:
        """Send a CRM screenshot to OpenAI Vision / Failover Router and return parsed customers."""
        if not image_path.exists() or image_path.stat().st_size == 0:
            raise ParserError("The uploaded image could not be read.")

        # When bypass_router is set (e.g. by a test fake), call the
        # client directly using the Responses API format. Production
        # always goes through the failover router.
        if self.bypass_router:
            image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
            mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
            response = await self.client.responses.create(
                model=self.settings.openai_model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": f"{SYSTEM_PROMPT}\n\n{AI_PROMPT}"},
                            {
                                "type": "input_image",
                                "image_url": f"data:{mime};base64,{image_data}",
                            },
                        ],
                    }
                ],
            )
            raw_json = _extract_json_array(response.output_text)
            return [_map_common_keys(customer) for customer in load_json_array(raw_json)]

        # Otherwise, route through failover router
        image_data = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{SYSTEM_PROMPT}\n\n{AI_PROMPT}"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{image_data}"},
                    },
                ],
            }
        ]
        output_text = await self.router.generate_response(messages, requires_vision=True)
        raw_json = _extract_json_array(output_text)
        return [_map_common_keys(customer) for customer in load_json_array(raw_json)]
