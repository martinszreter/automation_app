"""Email notification for new contact form submissions.

Sending is best-effort: any failure is logged and swallowed so the
contact form never breaks because of SMTP problems.
"""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.db.models import ContactRequest

logger = logging.getLogger(__name__)


def _build_message(contact: ContactRequest) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = settings.smtp_user
    msg["To"] = settings.contact_to
    msg["Subject"] = f"New contact: {contact.name} — {contact.interest or 'n/a'}"
    msg.set_content(
        "New contact request via startend.ch\n"
        "\n"
        f"Name:           {contact.name}\n"
        f"Company:        {contact.company or '-'}\n"
        f"Email:          {contact.email}\n"
        f"Interest:       {contact.interest or '-'}\n"
        f"Call requested: {'yes' if contact.call_requested else 'no'}\n"
        "\n"
        "Message:\n"
        f"{contact.message}\n"
    )
    return msg


def _send_sync(msg: EmailMessage) -> None:
    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.login(settings.smtp_user, settings.smtp_pass)
        smtp.send_message(msg)


async def send_contact_notification(contact: ContactRequest) -> None:
    """Send a notification email for a stored contact request. Never raises."""
    if not (settings.smtp_host and settings.smtp_user and settings.contact_to):
        logger.warning("SMTP not configured; skipping contact notification email")
        return
    try:
        msg = _build_message(contact)
        await asyncio.to_thread(_send_sync, msg)
    except Exception:
        logger.exception("Failed to send contact notification email")
