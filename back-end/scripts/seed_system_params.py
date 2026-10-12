"""Seed missing active prompts from code constants without replacing saved edits.

Run after migrations: python -m scripts.seed_system_params
"""
import asyncio

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.postgres import async_session
from app.models import SystemParam, generate_id
from app.prompts import PROMPT_DEFAULTS, validate_prompt


async def main():
    if async_session is None:
        raise SystemExit("DATABASE_URL não configurada.")
    async with async_session() as session:
        for key, value in PROMPT_DEFAULTS.items():
            validate_prompt(key, value)
        result = await session.execute(
            insert(SystemParam)
            .values([{"id": generate_id(), "param": key, "value": value} for key, value in PROMPT_DEFAULTS.items()])
            .on_conflict_do_nothing(index_elements=[SystemParam.param])
        )
        await session.commit()
        print(f"Prompts inseridos: {result.rowcount}.")
        prompts = (await session.execute(select(SystemParam).where(SystemParam.param.in_(PROMPT_DEFAULTS)))).scalars().all()
        values = {prompt.param: prompt.value for prompt in prompts}
        if set(values) != set(PROMPT_DEFAULTS):
            raise SystemExit("Não foi possível conferir todos os prompts do sistema.")
        for key in PROMPT_DEFAULTS:
            validate_prompt(key, values[key])
            source = "constante inicial" if values[key] == PROMPT_DEFAULTS[key] else "edição salva preservada"
            print(f"{key}: {len(values[key])} caracteres ({source}).")


if __name__ == "__main__":
    asyncio.run(main())
