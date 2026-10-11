"""Install after the provider enables pg_cron in the application database."""
import asyncio
from sqlalchemy import text
from app.db.postgres import async_engine
async def main():
    try:
        async with async_engine.begin() as connection:
            target = (await connection.execute(text("SELECT current_database()"))).scalar()
            configured = (await connection.execute(text("SELECT current_setting('cron.database_name', true)"))).scalar()
            if configured != target:
                raise SystemExit("No provedor, configure cron.database_name para o banco da aplicação, reinicie o compute e execute este script novamente. Use compute sempre ativo para garantir a execução diária.")
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_cron"))
            await connection.execute(text("SELECT cron.schedule('iformante-daily-retention', '0 3 * * *', 'SELECT public.cleanup_iformante_expired()')"))
            print("Cron instalado: 03:00 UTC, diariamente às 00:00 de São Paulo.")
    finally: await async_engine.dispose()
if __name__ == "__main__": asyncio.run(main())
