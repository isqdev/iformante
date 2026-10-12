from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.prompts import PROMPT_DEFAULTS, validate_prompt
from app.repositories.system_param_repository import SystemParamRepository
from app.security.auth import AuthError, normalize_email


async def list_prompts(session: AsyncSession):
    try:
        return await SystemParamRepository(session).list_prompts()
    except ValueError as error:
        raise AuthError(str(error), 503) from error


async def update_prompt(session: AsyncSession, param: str, value: str, expected_value: str):
    if param not in PROMPT_DEFAULTS:
        raise AuthError("Prompt não encontrado.", 404)
    try:
        validate_prompt(param, value)
    except ValueError as error:
        raise AuthError(str(error), 422) from error
    prompt = await SystemParamRepository(session).update_value(param, value, expected_value)
    if prompt is None:
        await session.rollback()
        raise AuthError("Este prompt mudou desde que você abriu o editor. Recarregue a versão salva antes de tentar novamente.", 409)
    await session.commit()
    return prompt


async def update_role(session: AsyncSession, actor_id: str, email: str, role: str):
    email = normalize_email(email)
    if role not in {"ADMIN", "SUPER"}:
        raise AuthError("Papel inválido.", 422)
    # Administrative role changes share this transaction lock across API instances.
    await session.execute(text("SELECT pg_advisory_xact_lock(202610120001)"))
    actor = await session.get(User, actor_id, populate_existing=True, with_for_update=True)
    if actor is None or not actor.email_verified or actor.role != "SUPER":
        raise AuthError("Acesso exclusivo para SUPER.", 403)
    target = (await session.execute(select(User).where(func.lower(User.email) == email).with_for_update())).scalar_one_or_none()
    if target is None:
        raise AuthError("Usuário não encontrado.", 404)
    if not target.email_verified:
        raise AuthError("O usuário precisa confirmar o e-mail antes de alterar o papel.", 409)
    if target.id == actor.id:
        raise AuthError("Você não pode alterar seu próprio papel.", 409)
    if target.role not in {"ADMIN", "SUPER"}:
        raise AuthError("Apenas administradores podem ser promovidos a SUPER.", 409)
    if target.role == role:
        await session.commit()
        return {"message": "O usuário já possui esse papel. Nenhuma alteração foi necessária.", "role": role}
    if role == "ADMIN":
        count = (await session.execute(select(func.count()).select_from(User).where(User.role == "SUPER", User.email_verified.is_(True)))).scalar_one()
        if count <= 1:
            raise AuthError("O último SUPER não pode ser rebaixado.", 409)
    target.role = role
    await session.commit()
    message = "Administrador promovido a SUPER com sucesso." if role == "SUPER" else "SUPER rebaixado a administrador com sucesso."
    return {"message": message, "role": role}
