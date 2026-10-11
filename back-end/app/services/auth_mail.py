import asyncio
import base64
from datetime import timedelta
from email.message import EmailMessage
import hashlib
import json
import logging
import os
import smtplib
import ssl

from sqlalchemy import select, update

from app.models.auth import EmailDelivery
from app.security.auth import AuthError, now

logger = logging.getLogger(__name__)


def smtp_ready() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM") and os.getenv("AUTH_SECRET"))


def cipher():
    from cryptography.fernet import Fernet
    secret = os.getenv("AUTH_SECRET", "")
    if len(secret) < 32:
        raise AuthError("Serviço de e-mail não configurado.", 503)
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


async def enqueue(session, email: str, subject: str, body: str, challenge: str, expires_at):
    if not smtp_ready():
        raise AuthError("O envio de e-mail ainda não está configurado.", 503)
    await session.execute(update(EmailDelivery).where(
        EmailDelivery.challenge_id == challenge, EmailDelivery.state == "PENDING",
    ).values(state="CANCELLED", payload=""))
    payload = cipher().encrypt(json.dumps({"to": email, "subject": subject, "body": body}).encode()).decode()
    session.add(EmailDelivery(payload=payload, challenge_id=challenge, expires_at=expires_at))


def send_message(payload: dict):
    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = payload["to"]
    message["Subject"] = payload["subject"]
    message.set_content(payload["body"])
    use_ssl = os.getenv("SMTP_SSL", "false").lower() == "true"
    port = int(os.getenv("SMTP_PORT", "465" if use_ssl else "587"))
    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    kwargs = {"context": ssl.create_default_context()} if use_ssl else {}
    with smtp_class(os.environ["SMTP_HOST"], port, timeout=20, **kwargs) as client:
        if not use_ssl and os.getenv("SMTP_STARTTLS", "true").lower() == "true":
            client.starttls(context=ssl.create_default_context())
        if os.getenv("SMTP_USERNAME"):
            client.login(os.environ["SMTP_USERNAME"], os.environ.get("SMTP_PASSWORD", ""))
        client.send_message(message)


async def deliver_pending(session_factory):
    async with session_factory() as session:
        async with session.begin():
            delivery = (await session.execute(select(EmailDelivery).where(
                EmailDelivery.state == "PENDING", EmailDelivery.next_attempt_at <= now(),
            ).order_by(EmailDelivery.next_attempt_at).limit(1).with_for_update(skip_locked=True))).scalar_one_or_none()
            if delivery is None:
                return
            if delivery.expires_at <= now():
                delivery.state, delivery.payload = "EXPIRED", ""
                return
            try:
                await asyncio.to_thread(send_message, json.loads(cipher().decrypt(delivery.payload.encode())))
                delivery.state, delivery.payload = "SENT", ""
            except Exception:
                # SMTP errors can contain addresses; log only a delivery ID.
                logger.warning("mail.delivery_failed id=%s", delivery.id)
                delivery.attempts += 1
                if delivery.attempts >= 5:
                    delivery.state, delivery.payload = "FAILED", ""
                else:
                    delivery.next_attempt_at = now() + timedelta(seconds=30 * 2 ** delivery.attempts)


async def mail_worker(session_factory):
    while True:
        try:
            await deliver_pending(session_factory)
        except Exception:
            logger.warning("mail.worker_unavailable")
        await asyncio.sleep(5)
