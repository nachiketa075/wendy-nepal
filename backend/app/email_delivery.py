"""Outgoing email, used only for password-reset links.

The adapter is chosen by EMAIL_DELIVERY. With "disabled" nothing is sent and
callers are told so; the API never reports an email as sent unless a real
provider accepted it.
"""

import datetime as dt
import logging
import re
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

from .config import get_settings

logger = logging.getLogger("wendy.email")

# Filled only by the "memory" adapter, which config restricts to automated tests.
TEST_OUTBOX: list[dict] = []


def delivery_enabled() -> bool:
    return get_settings().email_delivery != "disabled"


def is_real_delivery() -> bool:
    return get_settings().email_delivery == "smtp"


def send_email(to: str, subject: str, body: str) -> bool:
    """Returns True only if the configured adapter accepted the message."""
    settings = get_settings()
    mode = settings.email_delivery
    if mode == "disabled":
        return False
    if mode == "memory":
        TEST_OUTBOX.append({"to": to, "subject": subject, "body": body})
        return True
    if mode == "dev_file":
        # Development convenience: the message (including its link) goes to a
        # local file, never to the log and never to a real inbox.
        folder = Path(settings.dev_mailbox_dir)
        folder.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%S%f")
        safe = re.sub(r"[^a-z0-9]+", "-", to.lower()).strip("-")[:60]
        (folder / f"{stamp}-{safe}.txt").write_text(f"To: {to}\nSubject: {subject}\n\n{body}\n", encoding="utf-8")
        logger.info("dev mailbox: wrote one message to %s", folder)
        return True

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        # Port 465 speaks TLS from the first byte; other ports upgrade with STARTTLS.
        if settings.smtp_port == 465:
            smtp = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15)
        else:
            smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
        with smtp:
            if settings.smtp_port != 465:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        # Type of failure only: no recipient, link or message content in the log.
        logger.error("email delivery failed: %s", sys.exc_info()[0].__name__)
        return False
    return True
