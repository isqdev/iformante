"""One-time admin bootstrap. Password is entered securely, never stored in source."""
import asyncio
import getpass
from sqlalchemy import select
from app.db.postgres import async_session
from app.models import User
from app.security.password import hash_password


async def main():
    password = getpass.getpass("Senha inicial de isaque123: ")
    if not password:
        raise SystemExit("Senha obrigatória.")
    async with async_session() as session:
        user = await session.get(User, "isaque123")
        owner = (await session.execute(select(User).where(User.email == "20230006245@estudantes.ifpr.edu.br"))).scalar_one_or_none()
        if owner and owner.id != "isaque123":
            raise SystemExit("O e-mail já pertence a outra conta.")
        if user is None:
            user = User(id="isaque123", name="Isaque", email="20230006245@estudantes.ifpr.edu.br")
            session.add(user)
        elif user.email_verified and user.role == "ADMIN" and user.email == "20230006245@estudantes.ifpr.edu.br":
            print("Conta já provisionada; senha preservada.")
            return
        user.email = "20230006245@estudantes.ifpr.edu.br"
        user.role, user.email_verified, user.password_hash = "ADMIN", True, hash_password(password)
        await session.commit()
    print("Admin provisionado.")


if __name__ == "__main__":
    asyncio.run(main())
