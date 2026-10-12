from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_database_session
from app.dtos.system import SystemPromptResponse, UpdatePromptRequest, UpdateRoleRequest, UpdateRoleResponse
from app.models import User
from app.security.dependencies import require_super
from app.use_cases.system import list_prompts, update_prompt, update_role

router = APIRouter(prefix="/system", tags=["system"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
SuperUser = Annotated[User, Depends(require_super)]


@router.get("/prompts", response_model=list[SystemPromptResponse])
async def get_prompts(user: SuperUser, session: Session):
    return await list_prompts(session)


@router.patch("/prompts/{param}", response_model=SystemPromptResponse)
async def patch_prompt(param: str, payload: UpdatePromptRequest, user: SuperUser, session: Session):
    return await update_prompt(session, param, payload.value, payload.expected_value)


@router.patch("/users/role", response_model=UpdateRoleResponse)
async def patch_role(payload: UpdateRoleRequest, user: SuperUser, session: Session):
    return await update_role(session, user.id, payload.email, payload.role)
