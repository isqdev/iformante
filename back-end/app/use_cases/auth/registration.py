from datetime import timedelta
import hmac
import secrets

from sqlalchemy import func, select

from app.models import User
from app.models.auth import PendingRegistration, auth_id
from app.security.auth import AuthError, code_hash, normalize_email, now, validate_password
from app.security.password import hash_password
from app.services.auth_mail import enqueue


async def register(session, name: str, email: str, password: str, confirmation: str):
    email = normalize_email(email)
    validate_password(password, confirmation)
    name = " ".join(name.split())
    if not name:
        raise AuthError("Informe seu nome.")
    if (await session.execute(select(User.id).where(func.lower(User.email) == email))).scalar_one_or_none():
        raise AuthError("Já existe uma conta com esse e-mail.", 409)
    pending = (await session.execute(select(PendingRegistration).where(
        PendingRegistration.email == email,
    ).with_for_update())).scalar_one_or_none()
    if pending and pending.next_send_at > now():
        raise AuthError("Aguarde 60 segundos antes de reenviar.", 429)
    if pending is None:
        pending = PendingRegistration(id=auth_id(), email=email)
        session.add(pending)
    pending.name, pending.password_hash = name, hash_password(password)
    await send_code(session, pending)
    await session.commit()
    return {"registration_id": pending.id, "expires_in": 600, "resend_after": 60}


async def send_code(session, pending):
    code = f"{secrets.randbelow(1000):03d}"
    pending.code_hash = code_hash(pending.id, code)
    pending.expires_at = now() + timedelta(minutes=10)
    pending.next_send_at = now() + timedelta(seconds=60)
    await enqueue(session, pending.email, "Confirme seu cadastro no InFormante",
                  f"Seu código é {code}. Ele é válido por 10 minutos.", pending.id, pending.expires_at)


async def resend(session, registration_id):
    pending = await session.get(PendingRegistration, registration_id, with_for_update=True)
    if pending is None:
        raise AuthError("Cadastro pendente não encontrado.", 404)
    if pending.next_send_at > now():
        raise AuthError("Aguarde 60 segundos antes de reenviar.", 429)
    await send_code(session, pending)
    await session.commit()
    return {"expires_in": 600, "resend_after": 60}


async def confirm(session, registration_id, code):
    pending = await session.get(PendingRegistration, registration_id, with_for_update=True)
    if pending is None or pending.expires_at <= now():
        raise AuthError("Código expirado. Solicite outro envio.")
    if not hmac.compare_digest(pending.code_hash, code_hash(pending.id, code)):
        raise AuthError("Código incorreto.")
    if (await session.execute(select(User.id).where(func.lower(User.email) == pending.email))).scalar_one_or_none():
        raise AuthError("Já existe uma conta com esse e-mail.", 409)
    user = User(name=pending.name, email=pending.email, password_hash=pending.password_hash,
                role="COMMON" if pending.email.endswith("@estudantes.ifpr.edu.br") else "ADMIN", email_verified=True)
    session.add(user)
    await session.delete(pending)
    await session.commit()
    return {"message": "Cadastro confirmado. Você já pode entrar."}
