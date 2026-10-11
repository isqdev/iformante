from datetime import timedelta
import secrets

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_database_session
from app.dtos.auth import (ChangePasswordRequest, ConfirmRegistrationRequest, EmailRequest, LoginRequest,
                           PasswordRecoveryDTO, ProfileRequest, RegisterRequest, ResendRequest,
                           ResetPasswordRequest, ResetTokenRequest, UserProfileDTO)
from app.models import User
from app.models.auth import AuthSession
from app.security.auth import AuthError, mask_email, normalize_email, now, token_hash, user_profile
from app.security.dependencies import clear_session_cookies, optional_current_user, require_user, set_session_cookies
from app.security.password import verify_password
from app.use_cases.auth import passwords, registration

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=202)
async def register(payload: RegisterRequest, session: AsyncSession = Depends(get_database_session)):
    return await registration.register(session, payload.name, payload.email, payload.password, payload.confirm_password)


@router.post("/register/confirm")
async def confirm(payload: ConfirmRegistrationRequest, session: AsyncSession = Depends(get_database_session)):
    return await registration.confirm(session, payload.registration_id, payload.code)


@router.post("/register/resend", status_code=202)
async def resend(payload: ResendRequest, session: AsyncSession = Depends(get_database_session)):
    return await registration.resend(session, payload.registration_id)


@router.post("/login", response_model=UserProfileDTO)
async def login(payload: LoginRequest, response: Response, session: AsyncSession = Depends(get_database_session)):
    try:
        email = normalize_email(payload.email)
    except AuthError:
        raise HTTPException(401, "E-mail ou senha incorretos.")
    user = (await session.execute(select(User).where(func.lower(User.email) == email))).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "E-mail ou senha incorretos.")
    if not user.email_verified:
        raise HTTPException(403, "Confirme seu cadastro para entrar.")
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    session.add(AuthSession(token_hash=token_hash(token), user_id=user.id, csrf_token=csrf, expires_at=now() + timedelta(days=7)))
    await session.commit()
    set_session_cookies(response, token, csrf)
    return user_profile(user)


@router.get("/me", response_model=UserProfileDTO | None)
async def me(user: User | None = Depends(optional_current_user)):
    return user_profile(user) if user else None


@router.post("/logout")
async def logout(response: Response, user: User = Depends(require_user), session: AsyncSession = Depends(get_database_session)):
    # Revoking every device also guarantees that discarded cookies cannot recover private state.
    await session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    await session.commit()
    clear_session_cookies(response)
    return {"message": "Sessão encerrada."}


@router.patch("/profile", response_model=UserProfileDTO)
async def profile(payload: ProfileRequest, user: User = Depends(require_user), session: AsyncSession = Depends(get_database_session)):
    name = " ".join(payload.name.split())
    if not name:
        raise HTTPException(400, "Informe seu nome.")
    user.name = name
    await session.commit()
    return user_profile(user)


@router.post("/password/forgot", status_code=202)
async def forgot(payload: EmailRequest, session: AsyncSession = Depends(get_database_session)):
    return await passwords.forgot(session, payload.email)


@router.post("/password/reset/validate", response_model=PasswordRecoveryDTO)
async def validate_reset(payload: ResetTokenRequest, session: AsyncSession = Depends(get_database_session)):
    user = await passwords.reset_user(session, payload.token)
    return PasswordRecoveryDTO(masked_email=mask_email(user.email))


@router.post("/password/reset")
async def reset(payload: ResetPasswordRequest, response: Response, session: AsyncSession = Depends(get_database_session)):
    user = await passwords.reset_user(session, payload.token)
    await passwords.change(session, user, payload.password, payload.confirm_password)
    clear_session_cookies(response)
    return {"message": "Senha alterada. Entre novamente."}


@router.post("/password/change")
async def change_password(payload: ChangePasswordRequest, response: Response, user: User = Depends(require_user), session: AsyncSession = Depends(get_database_session)):
    await passwords.change(session, user, payload.password, payload.confirm_password, payload.current_password)
    clear_session_cookies(response)
    return {"message": "Senha alterada. Entre novamente."}
