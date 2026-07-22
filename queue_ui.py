"""Telegram UI for the queue engine."""

from __future__ import annotations

from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from formatting import format_currency
from logger import log
from queue_engine import QueueEngine, QueueSelection


def queue_from_context(context: ContextTypes.DEFAULT_TYPE) -> QueueEngine:
    return context.application.bot_data["queue_engine"]


def _call_button_rows(phone_numbers: list[str]) -> list[list[InlineKeyboardButton]]:
    """No tel: inline buttons are generated here.

    Telegram rejects tel: URLs in inline keyboard buttons, so the only
    supported tap-to-call experience is produced in render_customer() as
    message text hyperlinks (<a href="tel:...">). This helper is kept as
    a placeholder so the UI can still fallback to text-only mode if the
    button layout is ever extended again.

    IMPORTANT: Do not change this helper to emit tel: buttons without
    a full regression run against the Telegram Bot API. The send/retry
    fallback around _send_text_with_retry is the last defense against
    a broken queue send.
    """
    return []


def queue_keyboard(customer: dict | int) -> InlineKeyboardMarkup:
    if isinstance(customer, dict):
        customer_id = customer.get("id")
        phone_numbers = customer.get("phone_numbers") or []
        status = customer.get("status")
        has_warning = bool(customer.get("warning_note"))
    else:
        customer_id = customer
        phone_numbers = []
        status = None
        has_warning = False

    if status == "needs_review":
        # Missing name or phone -- can't safely call. Let the operator
        # decide instead of guessing or getting stuck.
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("⚠ Wrong Number", callback_data=f"queue_wrong:{customer_id}"),
                    InlineKeyboardButton("⏭ Skip", callback_data=f"queue_skip:{customer_id}"),
                ],
                [InlineKeyboardButton("🗑️ Delete", callback_data=f"queue_delete:{customer_id}")],
                [InlineKeyboardButton("ℹ️ More Info", callback_data=f"customer_view:{customer_id}")],
            ]
        )

    rows: list[list[InlineKeyboardButton]] = []
    rows.extend(_call_button_rows(phone_numbers))
    rows.append(
        [
            InlineKeyboardButton("✅ Contacted", callback_data=f"queue_warned:{customer_id}"),
            InlineKeyboardButton("❌ Didn't Answer", callback_data=f"queue_later:{customer_id}"),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton("⚠ Wrong Number", callback_data=f"queue_wrong:{customer_id}"),
            InlineKeyboardButton("⏭ Skip", callback_data=f"queue_skip:{customer_id}"),
        ]
    )
    if has_warning:
        # A same-day-recontact (or other) warning -- offer Delete too,
        # alongside the normal actions, instead of only auto-deciding.
        rows.append([InlineKeyboardButton("🗑️ Delete", callback_data=f"queue_delete:{customer_id}")])
    rows.append([InlineKeyboardButton("ℹ️ More Info", callback_data=f"customer_view:{customer_id}")])
    return InlineKeyboardMarkup(rows)


def completion_keyboard(has_call_backs: bool) -> InlineKeyboardMarkup:
    """Buttons shown once a queue finishes: Call Back (if anyone didn't answer) and New Call List."""
    row = []
    if has_call_backs:
        row.append(InlineKeyboardButton("🔁 Call Back", callback_data="queue_call_back"))
    row.append(InlineKeyboardButton("🆕 New Call List", callback_data="new_call_list"))
    return InlineKeyboardMarkup([row])


def _strip_tel_buttons(reply_markup: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    # VITAL: this fallback path is relied on when Telegram rejects tel: URLs
    # in inline keyboard buttons. Do not remove or alter this logic without
    # verifying the full send/retry behavior, because it is the last line of
    # defense against a broken queue message send.
    rows: list[list[InlineKeyboardButton]] = []
    for row in reply_markup.inline_keyboard:
        safe_row = [button for button in row if not (button.url and button.url.startswith("tel:"))]
        if safe_row:
            rows.append(safe_row)
    if not rows:
        return InlineKeyboardMarkup(None)
    return InlineKeyboardMarkup(rows)


def _send_text_with_retry(message, text: str, reply_markup: InlineKeyboardMarkup | None):
    async def _send(method):
        try:
            return await method(
                text,
                reply_markup=reply_markup,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except TelegramError:
            if reply_markup is None:
                raise
            safe_markup = _strip_tel_buttons(reply_markup)
            if safe_markup.inline_keyboard == reply_markup.inline_keyboard:
                raise
            log.exception("Telegram send failed with tel: inline buttons; retrying without them")
            return await method(
                text,
                reply_markup=safe_markup,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )

    return _send


def _phone_text_line(phones: list[str]) -> str:
    """Phone numbers as tel: hyperlinks in the message TEXT -- a documented
    safe fallback reference alongside the primary Call button(s)."""
    if not phones:
        return "No phone on file"
    links = [f'<a href="tel:{escape(phone)}">{escape(phone)}</a>' for phone in phones]
    return ", ".join(links)


def render_customer(customer: dict, progress) -> str:
    full_name = f"{customer['first_name']} {customer['last_name']}".strip() or "(name missing)"
    phones = customer.get("phone_numbers") or []

    header = f"Client {progress.current_position}/{progress.total_customers}     {progress.percent}%"

    body = [
        header,
        "",
        f"👤 {escape(full_name)}",
        "",
        f"Loan #: {escape(customer['loan_number'])}",
        f"Balance: {escape(format_currency(customer.get('balance')))}",
        f"Days Overdue: {escape(customer['days_overdue'])}",
    ]

    if customer.get("monthly_payment"):
        body.append(f"Monthly Payment: {escape(format_currency(customer['monthly_payment']))}")
    if customer.get("current_overdue_amount"):
        body.append(f"Amount Overdue: {escape(format_currency(customer['current_overdue_amount']))}")

    body.append(f"Phone: {_phone_text_line(phones)}")

    if customer.get("warning_note"):
        body.append("")
        body.append(f"⚠️ {escape(customer['warning_note'])}")

    body.extend(["", "Choose an action. Tap ℹ️ More Info for full loan details and history."])
    return "\n".join(body)


def render_status(progress) -> str:
    return (
        f"Customers Remaining: {progress.remaining}\n"
        f"Customers Contacted: {progress.contacted}\n"
        f"Customers Didn't Answer: {progress.did_not_answer}\n"
        f"Progress {progress.percent}%"
    )


def _completion_text(queue: QueueEngine, telegram_user_id: int | None) -> str:
    return (
        queue.session_completion_summary(telegram_user_id=telegram_user_id)
        or queue.completion_summary()
    )


async def send_or_edit_queue_message(message, selection: QueueSelection) -> None:
    queue = None
    if selection.complete:
        queue = "complete"
        text = "Session Complete"
        reply_markup = None
    elif selection.paused:
        text = "Queue paused."
        reply_markup = None
    elif selection.customer:
        text = render_customer(selection.customer, selection.progress)
        reply_markup = queue_keyboard(selection.customer)
    else:
        text = "No waiting customers."
        reply_markup = None

    try:
        await _send_text_with_retry(message, text, reply_markup)(message.edit_text)
    except TelegramError:
        log.exception("Telegram edit failed, sending a new message")
        sent = await _send_text_with_retry(message, text, reply_markup)(message.reply_text)
        return sent
    return queue


async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    queue = queue_from_context(context)
    queue.pause(telegram_user_id=update.effective_user.id if update.effective_user else None)
    await update.effective_message.reply_text("Queue paused.")


async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    queue = queue_from_context(context)
    telegram_user_id = update.effective_user.id if update.effective_user else None
    selection = queue.resume(telegram_user_id=telegram_user_id)

    if selection.complete:
        await update.effective_message.reply_text(
            _completion_text(queue, telegram_user_id),
            reply_markup=completion_keyboard(selection.progress.did_not_answer > 0),
        )
        return

    if selection.customer is None:
        await update.effective_message.reply_text("No customers loaded. Use /upload to get started.")
        return

    sent = await _send_text_with_retry(
        update.effective_message,
        render_customer(selection.customer, selection.progress),
        queue_keyboard(selection.customer),
    )(update.effective_message.reply_text)
    queue.set_message_reference(sent.chat_id, sent.message_id)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    queue = queue_from_context(context)
    await update.effective_message.reply_text(render_status(queue.status()))


async def handle_queue_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    queue = queue_from_context(context)
    telegram_user_id = getattr(getattr(query, "from_user", None), "id", None)

    try:
        await query.answer()
        parts = query.data.split(":", 1)
        action = parts[0]
        raw_customer_id = parts[1] if len(parts) > 1 else None

        if action == "queue_call_back":
            selection = queue.restart_call_later(telegram_user_id=telegram_user_id)
            if selection.complete:
                await query.edit_message_text(
                    "No customers to call back.\n\n" + _completion_text(queue, telegram_user_id),
                    reply_markup=completion_keyboard(False),
                )
            elif selection.customer:
                await query.edit_message_text(
                    render_customer(selection.customer, selection.progress),
                    reply_markup=queue_keyboard(selection.customer),
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            return

        if action == "queue_warned":
            selection = queue.apply_action(
                int(raw_customer_id),
                "warned",
                telegram_user_id=telegram_user_id,
            )
        elif action == "queue_later":
            selection = queue.apply_action(
                int(raw_customer_id),
                "call_later",
                telegram_user_id=telegram_user_id,
            )
        elif action == "queue_skip":
            selection = queue.apply_action(
                int(raw_customer_id),
                "skip",
                telegram_user_id=telegram_user_id,
            )
        elif action == "queue_wrong":
            selection = queue.apply_action(
                int(raw_customer_id),
                "invalid_number",
                telegram_user_id=telegram_user_id,
            )
        elif action == "queue_delete":
            selection = queue.delete_customer(
                int(raw_customer_id),
                telegram_user_id=telegram_user_id,
            )
        else:
            return

        if selection.complete:
            await query.edit_message_text(
                _completion_text(queue, telegram_user_id),
                reply_markup=completion_keyboard(selection.progress.did_not_answer > 0),
            )
        elif selection.customer:
            await query.edit_message_text(
                render_customer(selection.customer, selection.progress),
                reply_markup=queue_keyboard(selection.customer),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
    except Exception:
        log.exception("Queue callback failed")
        await query.message.reply_text("Something went wrong. Use /resume to continue.")
