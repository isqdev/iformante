from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_param import SystemParam
from app.prompts import PROMPT_DEFAULTS, PromptSnapshot


class SystemParamRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_prompts(self) -> list[SystemParam]:
        result = await self.session.execute(select(SystemParam).where(SystemParam.param.in_(PROMPT_DEFAULTS)))
        prompts = {prompt.param: prompt for prompt in result.scalars()}
        if set(prompts) != set(PROMPT_DEFAULTS):
            raise ValueError("Prompts do sistema não configurados. Aplique a migração do banco.")
        return [prompts[key] for key in PROMPT_DEFAULTS]

    async def snapshot(self) -> PromptSnapshot:
        return PromptSnapshot.from_values({prompt.param: prompt.value for prompt in await self.list_prompts()})

    async def update_value(self, param: str, value: str, expected_value: str) -> SystemParam | None:
        result = await self.session.execute(
            update(SystemParam)
            .where(SystemParam.param == param, SystemParam.value == expected_value)
            .values(value=value)
            .returning(SystemParam)
            .execution_options(synchronize_session="fetch")
        )
        return result.scalar_one_or_none()
