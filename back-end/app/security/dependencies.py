import hmac
import os

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_database_session
from app.models import User
from app.models.auth import AuthSession
from app.security.auth import CSRF_COOKIE, SESSION_COOKIE, now, token_hash


async def optional_current_user(request: Request, session: AsyncSession = Depends(get_database_session)) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    auth_session = await session.get(AuthSession, token_hash(token))
    if not auth_session or auth_session.expires_at <= now():
        return None
    user = await session.get(User, auth_session.user_id)
    if not user or not user.email_verified:
        return None
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        supplied = request.headers.get("x-csrf-token", "")
        if not supplied or not hmac.compare_digest(supplied, auth_session.csrf_token):
            raise HTTPException(403, "Requisição inválida. Atualize a página.")
    return user


async def require_user(user: User | None = Depends(optional_current_user)) -> User:
    if not user:
        raise HTTPException(401, "Entre para continuar.")
    return user


async def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != "ADMIN":
        raise HTTPException(403, "Acesso exclusivo para Admin.")
    return user


def set_session_cookies(response, token, csrf):
    options = dict(path="/", secure=os.getenv("COOKIE_SECURE", "false").lower() == "true", samesite="lax", max_age=604800)
    response.set_cookie(SESSION_COOKIE, token, httponly=True, **options)
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, **options)


def clear_session_cookies(response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
