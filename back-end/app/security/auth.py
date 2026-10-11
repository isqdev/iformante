from datetime import UTC, datetime
import hashlib
import hmac
import os
import re

from app.models.user import User

SESSION_COOKIE = "iformante_session"
CSRF_COOKIE = "iformante_csrf"


class AuthError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def now() -> datetime:
    return datetime.now(UTC)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def normalize_email(email: str) -> str:
    value = email.strip().lower()
    if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@(estudantes\.ifpr\.edu\.br|ifpr\.edu\.br)", value):
        raise AuthError("Use um e-mail institucional do IFPR.")
    local, _ = value.split("@")
    if len(value) > 255 or local.startswith(".") or local.endswith(".") or ".." in local:
        raise AuthError("Informe um e-mail válido.")
    return value


def validate_password(password: str, confirmation: str) -> None:
    if len(password) < 8:
        raise AuthError("A senha deve ter pelo menos 8 caracteres.")
    if password != confirmation:
        raise AuthError("As senhas não coincidem.")


def mask_email(email: str) -> str:
    local = email.split("@", 1)[0]
    return "••••••" + local[-3:]


def user_profile(user: User) -> dict:
    return {"id": user.id, "first_name": next(iter(user.name.split()), "Usuário"), "role": user.role}


def code_hash(challenge: str, code: str) -> str:
    secret = os.environ.get("AUTH_SECRET", "")
    if len(secret) < 32:
        raise AuthError("Serviço de cadastro não configurado.", 503)
    return hmac.new(secret.encode(), f"{challenge}:{code}".encode(), hashlib.sha256).hexdigest()
