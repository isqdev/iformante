from datetime import timedelta
import os
import secrets

from sqlalchemy import delete, func, select

from app.models import User
from app.models.auth import AuthSession, PasswordReset
from app.security.auth import AuthError, normalize_email, now, token_hash, validate_password
from app.security.password import hash_password, verify_password
from app.services.auth_mail import enqueue, smtp_ready


async def forgot(session, email):
    email = normalize_email(email)
    if not smtp_ready():
        raise AuthError("O envio de e-mail ainda não está configurado.", 503)
    user = (await session.execute(select(User).where(func.lower(User.email) == email, User.email_verified.is_(True)).with_for_update())).scalar_one_or_none()
    if user:
        await session.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id))
        token = secrets.token_urlsafe(32)
        expires = now() + timedelta(minutes=30)
        session.add(PasswordReset(token_hash=token_hash(token), user_id=user.id, expires_at=expires))
        url = os.getenv("APP_PUBLIC_URL", "http://localhost:3000").rstrip("/") + "/recuperar-senha/redefinir?token=" + token
        await enqueue(session, user.email, "Redefina sua senha no InFormante",
                      f"Abra este link para definir uma nova senha:\n{url}\n\nVálido por 30 minutos. Se não solicitou, ignore esta mensagem.",
                      "reset:" + user.id, expires)
        await session.commit()
    return {"message": "Se houver uma conta, enviaremos as instruções para seu e-mail."}


async def reset_user(session, token):
    reset = await session.get(PasswordReset, token_hash(token), with_for_update=True)
    if not reset or reset.expires_at <= now():
        raise AuthError("Link inválido ou expirado. Solicite outro envio.")
    user = await session.get(User, reset.user_id, with_for_update=True)
    if not user:
        raise AuthError("Link inválido.")
    return user


async def change(session, user, password, confirmation, current_password=None):
    validate_password(password, confirmation)
    if current_password is not None and not verify_password(current_password, user.password_hash):
        raise AuthError("A senha atual está incorreta.")
    user.password_hash = hash_password(password)
    await session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    await session.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id))
    await session.commit()
